"""Deterministic benchmark harness for the RENDER pipeline only.

Measures exactly the work ``src.main.run`` charges to the renderer:
``TemporalSmoother.smooth`` -> ``resize_rgb24_area`` -> ``render_frame`` /
``render_frame_blocks`` -> sink write. FFmpeg decoding, the playback clock,
frame selection and pacing are deliberately excluded, so numbers are stable
enough to compare across code edits on the same machine.

Frames are synthetic and generated from a fixed seed, so every run feeds
byte-identical input into every pipeline. Real terminal I/O is excluded too
(see the note printed with the results) because its cost is machine-, OS- and
terminal-emulator-specific, which would make before/after comparisons invalid.

Usage:
    python bench.py --json bench_baseline.json
    python bench.py --baseline bench_baseline.json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time

from src.config import Config
from src.renderer import RGBAsciiRenderer, resize_rgb24_area
from src.smoothing import TemporalSmoother

# Fixed seed: synthetic frames are reproducible byte-for-byte across runs.
# No os.urandom, no unseeded random().
SEED = 0x5EED1234

# Realistic decode source (a 360p video is what the player actually feeds in).
# The player asks FFmpeg for frames at the ASCII grid size, so in steady-state
# playback src == dst and the resize stage is skipped entirely -- it only runs on
# a live terminal resize. The default therefore matches the largest default grid
# so the run measures what the player actually does, and the smoothing/render
# costs this project has been optimising are not buried under ~30-70 ms/frame of
# area resize (with a resize-heavy source almost every row just reports OVER the
# 33.3 ms budget, which tells you nothing). Use `--src 640x360` to measure the
# terminal-resize path instead.
DEFAULT_SRC = (160, 48)

# Source dimensions the pipeline reads; main() rebinds these from --src.
SRC_WIDTH, SRC_HEIGHT = DEFAULT_SRC

# Frames per timed pass. More than one so temporal smoothing blends for real.
FRAMES_PER_PASS = 3

# Discarded passes before timing starts (caches, smoothing state, CPU ramp).
WARMUP_PASSES = 2

DEFAULT_SIZES = "80x22,120x38,160x48"
BUDGET_MS = 1000.0 / 30.0  # 30 FPS target

_LCG_A = 6364136223846793005
_LCG_C = 1442695040888963407
_LCG_M = (1 << 64) - 1

_TERMINAL_NOTE = """\
NOTE: a real terminal's write cost is NOT measured. Terminal cost is dominated
by VT100/ANSI parsing, the OS console API, screen refresh and TTY buffering --
all machine-, OS- and terminal-emulator-specific and inherently noisy, so
including it would make before/after comparisons meaningless. "null" sink
measures call overhead only; "bytes" sink measures the UTF-8 encode + memory
copy half of the write path (which a real terminal also pays).
total_ms excludes the sink; total_with_write_ms includes it.
bytes/frm is the UTF-8 length of the last frame of a pass started from a FRESH
smoother, so it is identical for every --repeat (it does not depend on how many
timed passes ran). smooth_off rows are stateless; smooth_on rows are not -- their
smoother carries state across calls, which is why the byte probe is separate
from the timing loop."""


def synthetic_frame(width: int, height: int, index: int) -> bytes:
    """Return a deterministic RGB24 frame of ``width`` x ``height``.

    Identical arguments always produce identical bytes (pure 64-bit LCG, seeded
    from SEED and the frame index). Colors vary with position, so adjacent
    pixels always differ -- a flat or low-entropy image would understate the
    cost of any per-pixel work, especially color deduplication.
    """
    state = (SEED + index * 0x9E3779B97F4A7C15) & _LCG_M
    out = bytearray(width * height * 3)
    for i in range(len(out)):
        state = (state * _LCG_A + _LCG_C) & _LCG_M
        out[i] = ((state >> 40) ^ state) & 0xFF
    return bytes(out)


class NullSink:
    """Discards the frame string: measures call overhead only."""

    __slots__ = ()

    def write(self, text: str) -> None:
        pass


class BytesSink:
    """Encodes the frame to an in-memory buffer, keeping only the last one."""

    __slots__ = ("last",)

    def __init__(self) -> None:
        self.last = b""

    def write(self, text: str) -> None:
        self.last = text.encode("utf-8")


def make_sink(name: str) -> NullSink | BytesSink:
    return NullSink() if name == "null" else BytesSink()


def parse_sizes(text: str) -> list[tuple[int, int]]:
    """Parse ``--sizes`` as a comma-separated list of ``WxH`` terminal grids."""
    out: list[tuple[int, int]] = []
    for part in text.split(","):
        part = part.strip().lower()
        if not part:
            continue
        w, _, h = part.partition("x")
        try:
            width, height = int(w), int(h)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"bad size {part!r}, expected WxH (e.g. 120x38)"
            )
        if width < 1 or height < 1:
            raise argparse.ArgumentTypeError(f"bad size {part!r}: must be positive")
        out.append((width, height))
    if not out:
        raise argparse.ArgumentTypeError("--sizes needs at least one WxH entry")
    return out


def parse_size(text: str) -> tuple[int, int]:
    """Parse a single ``WxH`` grid size."""
    return parse_sizes(text)[0]


def build_configs(sizes: list[tuple[int, int]]) -> list[dict]:
    """Return the configuration matrix: mono/true-color per size, plus blocks
    at the largest requested size, each with smoothing off and on."""
    largest = max(sizes)
    configs: list[dict] = []
    for width, height in sizes:
        configs += [
            {"id": f"{width}x{height}/mono/smooth_off", "width": width,
             "height": height, "mode": "mono", "smoothing": False, "blocks": False},
            {"id": f"{width}x{height}/mono/smooth_on", "width": width,
             "height": height, "mode": "mono", "smoothing": True, "blocks": False},
            {"id": f"{width}x{height}/color/smooth_off", "width": width,
             "height": height, "mode": "color", "smoothing": False, "blocks": False},
            {"id": f"{width}x{height}/color/smooth_on", "width": width,
             "height": height, "mode": "color", "smoothing": True, "blocks": False},
        ]
        if (width, height) == largest:
            configs += [
                {"id": f"{width}x{height}/blocks/smooth_off", "width": width,
                 "height": height, "mode": "blocks", "smoothing": False, "blocks": True},
                {"id": f"{width}x{height}/blocks/smooth_on", "width": width,
                 "height": height, "mode": "blocks", "smoothing": True, "blocks": True},
            ]
    return configs


def run_pass(
    frames: list[bytes],
    smoother: TemporalSmoother,
    renderer: RGBAsciiRenderer,
    dst_width: int,
    dst_height: int,
    blocks: bool,
    sink: NullSink | BytesSink,
) -> dict:
    """Run one pass over every frame, timing each pipeline stage separately.

    Stage order mirrors ``src.main.run``: smoothing happens on the decoded
    frame (before any resize), exactly as the player does it.
    """
    src_w, src_h = SRC_WIDTH, SRC_HEIGHT
    # Half-block mode pairs two source rows per cell, so the render target has
    # double the rows (mirrors main.render_resized_blocks_frame).
    rw = dst_width
    rh = dst_height * 2 if blocks else dst_height
    smooth_ms = resize_ms = render_ms = write_ms = 0.0
    out_bytes = 0
    for frame in frames:
        t0 = time.perf_counter()
        smoothed = smoother.smooth(frame)
        t1 = time.perf_counter()
        if (src_w, src_h) == (rw, rh):
            small = smoothed
        else:
            small = resize_rgb24_area(smoothed, src_w, src_h, rw, rh)
        t2 = time.perf_counter()
        if blocks:
            out = renderer.render_frame_blocks(small, rw, dst_height)
        else:
            out = renderer.render_frame(small, rw, rh)
        t3 = time.perf_counter()
        sink.write(out)
        t4 = time.perf_counter()
        smooth_ms += t1 - t0
        resize_ms += t2 - t1
        render_ms += t3 - t2
        write_ms += t4 - t3
        out_bytes = len(out.encode("utf-8"))

    n = len(frames)
    smooth_ms *= 1000.0 / n
    resize_ms *= 1000.0 / n
    render_ms *= 1000.0 / n
    write_ms *= 1000.0 / n
    total_ms = smooth_ms + resize_ms + render_ms
    return {
        "smooth_ms": smooth_ms,
        "resize_ms": resize_ms,
        "render_ms": render_ms,
        "write_ms": write_ms,
        "total_ms": total_ms,
        "total_with_write_ms": total_ms + write_ms,
        "fps": 1000.0 / total_ms if total_ms > 0 else float("inf"),
        "output_bytes": out_bytes,
    }


def build_rig(config: dict) -> dict:
    """Return the long-lived objects one configuration needs while measuring."""
    cfg = Config(
        enable_color=config["mode"] != "mono",
        smoothing=0.5 if config["smoothing"] else 0.0,
        blocks=config["blocks"],
    )
    return {
        "config": config,
        "renderer": RGBAsciiRenderer(cfg),
        "smoother": TemporalSmoother(cfg),
    }


def measure_all(
    configs: list[dict], frames: list[bytes], repeat: int, sink
) -> list[dict]:
    """Best-of-``repeat`` for every configuration, measured interleaved.

    Passes are interleaved (one pass of every config, then the next) rather
    than run config-by-config: this machine drifts, and a drift then hits every
    configuration equally instead of penalising whichever one happened to run
    during the slow period. That is what makes the numbers comparable to a
    baseline taken in an earlier process.

    Two discarded warmup passes run first, so lazily built caches (character
    tables, box ranges) are not billed to the reported numbers, and every timed
    pass does a real smoothing blend -- the very first ``smooth()`` call only
    initializes the retained state and skips the blend loop entirely.
    """
    rigs = [build_rig(cfg) for cfg in configs]
    best: list[dict | None] = [None] * len(rigs)
    for index in range(repeat + WARMUP_PASSES):
        for i, rig in enumerate(rigs):
            config = rig["config"]
            result = run_pass(
                frames,
                rig["smoother"],
                rig["renderer"],
                config["width"],
                config["height"],
                config["blocks"],
                sink,
            )
            if index < WARMUP_PASSES:
                continue
            current = best[i]
            if current is None or result["total_ms"] < current["total_ms"]:
                best[i] = result
    # output_bytes is a correctness check, not a timing sample, so it is taken
    # from a dedicated pass over a FRESH rig rather than from the timing loop.
    # A stateful config (smoothing > 0) carries smoother state across calls and
    # the rig is built once for the whole run, so by the last timed pass the
    # smoother has already seen (repeat + WARMUP_PASSES) * len(frames) frames
    # and has not necessarily converged. Reading the byte count out of whichever
    # pass won on wall clock -- or even out of the last pass -- therefore made
    # it a function of --repeat: the same code reported 314,588 and 314,586
    # bytes for 160x48/blocks/smooth_on at --repeat 1 vs 4. A fresh rig makes
    # the number a pure function of (--src, --sizes, mode, smoothing) and does
    # not perturb any timing measurement. Stateless rows are unaffected either
    # way; measuring them the same way keeps the column consistent.
    output_bytes = {}
    for config in configs:
        probe = build_rig(config)
        output_bytes[config["id"]] = run_pass(
            frames,
            probe["smoother"],
            probe["renderer"],
            config["width"],
            config["height"],
            config["blocks"],
            sink,
        )["output_bytes"]
    results = []
    for config, best_pass in zip(configs, best):
        assert best_pass is not None
        best_pass["id"] = config["id"]
        best_pass["width"] = config["width"]
        best_pass["height"] = config["height"]
        best_pass["mode"] = config["mode"]
        best_pass["smoothing"] = config["smoothing"]
        best_pass["blocks"] = config["blocks"]
        best_pass["output_bytes"] = output_bytes[config["id"]]
        best_pass["cells"] = config["width"] * config["height"]
        results.append(best_pass)
    return results


def print_table(results: list[dict], baseline: dict[str, dict]) -> None:
    """Print the human-readable table with an optional before/after column."""
    header = ("configuration", "smooth", "resize", "render", "write",
              "total", "FPS", "bytes/frm", "budget", "vs base")
    rows = []
    for r in results:
        if r["total_ms"] > BUDGET_MS:
            budget = f"OVER {r['total_ms'] / BUDGET_MS:.1f}x"
        else:
            budget = "ok"
        base = baseline.get(r["id"])
        if base is None or not base.get("total_ms"):
            delta = "new"
        else:
            pct = (base["total_ms"] - r["total_ms"]) / base["total_ms"] * 100.0
            delta = f"{pct:+.1f}%"
        rows.append((
            r["id"],
            f"{r['smooth_ms']:.3f}",
            f"{r['resize_ms']:.3f}",
            f"{r['render_ms']:.3f}",
            f"{r['write_ms']:.3f}",
            f"{r['total_ms']:.3f}",
            f"{r['fps']:.1f}",
            f"{r['output_bytes']:,}",
            budget,
            delta,
        ))
    widths = [
        max(len(header[i]), max(len(row[i]) for row in rows))
        for i in range(len(header))
    ]
    line = "  ".join(h.ljust(w) for h, w in zip(header, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))
    print()


# Run-metadata keys that decide *what work* a row measured. Two runs that
# differ on any of these measured different pipelines, so a before/after
# percentage between them is worse than no number at all: comparing a
# 640x360->80x22 baseline (which pays an area resize on every frame) against an
# 80x22 run (which does not) reports a fake ~30 ms/frame speedup. "sizes" is
# deliberately not one of these -- a run may add or drop a size, and the rows
# that still exist remain comparable.
_COMPARABLE_KEYS = ("src", "sink", "seed", "frames_per_pass", "warmup_passes")


def load_baseline(path: str | None, meta: dict) -> dict[str, dict]:
    """Load a previous run's results keyed by configuration id.

    The baseline is rejected outright when it did not measure the same work, so
    the before/after column can never quietly mix incompatible runs.
    """
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"# baseline {path!r} unusable ({exc}); showing absolute numbers only",
              file=sys.stderr)
        return {}
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        print(f"# baseline {path!r} is not a bench results file "
              "(no 'results' list); showing absolute numbers only", file=sys.stderr)
        return {}
    base_meta = data.get("meta")
    if not isinstance(base_meta, dict):
        print(f"# baseline {path!r} carries no run metadata, so it cannot be checked "
              "for comparability; showing absolute numbers only", file=sys.stderr)
        return {}
    diffs = [f"{key}: baseline {base_meta.get(key)!r} != current {meta.get(key)!r}"
             for key in _COMPARABLE_KEYS
             if base_meta.get(key) != meta.get(key)]
    if diffs:
        print(f"# baseline {path!r} measured different work; showing absolute numbers "
              "only (no before/after column):", file=sys.stderr)
        for d in diffs:
            print(f"#   {d}", file=sys.stderr)
        return {}
    return {r["id"]: r for r in data["results"] if isinstance(r, dict) and "id" in r}


def main(argv: list[str] | None = None) -> int:
    global SRC_WIDTH, SRC_HEIGHT
    parser = argparse.ArgumentParser(
        prog="python bench.py",
        description="Deterministic render-pipeline benchmark (no FFmpeg, no terminal).",
    )
    parser.add_argument("--json", metavar="out.json",
                        help="write machine-readable results to this file")
    parser.add_argument("--repeat", type=int, default=7, metavar="N",
                        help="timed passes per configuration, best-of (default 7)")
    parser.add_argument("--sizes", type=parse_sizes, default=parse_sizes(DEFAULT_SIZES),
                        metavar="W1xH1,W2xH2",
                        help=f"terminal grids to test (default {DEFAULT_SIZES})")
    parser.add_argument("--sink", choices=("null", "bytes"), default="null",
                        help="frame-write sink: discard (default) or in-memory bytes")
    parser.add_argument("--src", type=parse_size, default=DEFAULT_SRC,
                        metavar="WxH",
                        help=f"decode source size (default {DEFAULT_SRC[0]}x"
                             f"{DEFAULT_SRC[1]}); use a size matching --sizes to "
                             "measure steady-state playback, where no resize happens")
    parser.add_argument("--baseline", metavar="FILE",
                        help="previous results JSON; adds a before/after column")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    SRC_WIDTH, SRC_HEIGHT = args.src

    sink = make_sink(args.sink)
    meta = {
        "seed": SEED,
        "src": f"{SRC_WIDTH}x{SRC_HEIGHT}",
        "sizes": [f"{w}x{h}" for w, h in args.sizes],
        "repeat": args.repeat,
        "warmup_passes": WARMUP_PASSES,
        "frames_per_pass": FRAMES_PER_PASS,
        "sink": args.sink,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "budget_ms": BUDGET_MS,
        "excludes": ["ffmpeg decode", "frame selection", "pacing",
                     "real terminal write"],
    }
    baseline = load_baseline(args.baseline, meta)
    frames = [synthetic_frame(SRC_WIDTH, SRC_HEIGHT, i) for i in range(FRAMES_PER_PASS)]

    results = measure_all(build_configs(args.sizes), frames, args.repeat, sink)

    print(f"bench: src {SRC_WIDTH}x{SRC_HEIGHT} -> {len(args.sizes)} sizes, "
          f"best-of-{args.repeat} interleaved + {WARMUP_PASSES} warmup, "
          f"{FRAMES_PER_PASS} frames/pass, seed 0x{SEED:X}, sink={args.sink}")
    print(f"python {platform.python_version()} on {platform.system()} "
          f"({platform.machine()})\n")
    print_table(results, baseline)
    print(_TERMINAL_NOTE)

    if args.json:
        payload = {
            "schema": 1,
            "meta": meta,
            "results": results,
        }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
