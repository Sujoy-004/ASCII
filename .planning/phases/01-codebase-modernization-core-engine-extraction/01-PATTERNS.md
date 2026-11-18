# Phase 1: Codebase Modernization & Core Engine Extraction - Pattern Map

**Mapped:** 2026-11-17
**Files analyzed:** 14 (2 deleted, 10 modified, 2 verified-no-change)
**Analogs found:** 12 / 12 target files with tracked in-repo analogs

> **CRITICAL GROUND TRUTH — READ BEFORE PLANNING**
> The Phase 1 transformation is **already implemented and committed** on this branch.
> Commit `2a19dea feat(01-01): prune terminal module, decouple main into headless sink, export core facade`
> (followed by docs/verification commits `2a95997`, `f1e3f82`, `39b9ed9`, `79f8408`) produced:
>
> - `src/terminal.py` and `tests/test_terminal.py` **already deleted** (untracked in `git ls-files`).
> - `src/__init__.py` facade, `src/main.py` headless sink, `src/config.py` without `status_rows`, and
>   `tests/test_facade.py` **already in their target state** (verified by direct read of every file below).
>
> Therefore the analogs for this refactor phase are the **current tracked files themselves** — every
> analog path below was verified tracked via `git ls-files`. Plans built from this map should
> **verify/extend/harden** the existing state, not re-create it. Any plan step that says "delete
> `src/terminal.py`" or "create `src/__init__.py`" is stale and must be rewritten as a verification step
> against the excerpts in this document.

## File Classification

| New/Modified File | Action | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|--------|------|-----------|----------------|---------------|
| `src/terminal.py` | DELETE (D-01) | middleware (TUI) | event-driven | git history: `git show 2a19dea^:src/terminal.py` | none-in-tree (already deleted) |
| `tests/test_terminal.py` | DELETE (D-05) | test | request-response | git history: `git show 2a19dea^:tests/test_terminal.py` | none-in-tree (already deleted) |
| `src/main.py` | MODIFY (D-01) | controller (CLI entry) | request-response + streaming | `src/main.py` (self, post-refactor) | exact (in-place) |
| `src/__init__.py` | CREATE/MODIFY (D-03) | provider (facade) | transform (re-export) | `src/__init__.py` (self, post-refactor) | exact (in-place) |
| `src/config.py` | MODIFY (D-01/Pitfall 2) | config (dataclass) | CRUD | `src/config.py` (self, post-refactor) | exact (in-place) |
| `src/renderer.py` | MODIFY (discretion) | service (pure algorithm) | transform | `src/renderer.py` (self) | exact (in-place) |
| `src/video.py` | MODIFY (discretion) | service (subprocess reader) | streaming | `src/video.py` (self) | exact (in-place) |
| `src/audio.py` | MODIFY (discretion) | service (subprocess player) | event-driven | `src/audio.py` (self) | exact (in-place) |
| `tests/test_cleanup.py` | MODIFY (D-05) | test | request-response | `tests/test_cleanup.py` (self, pruned) | exact (in-place) |
| `tests/test_playback.py` | MODIFY (D-05) | test | request-response | `tests/test_playback.py` (self, pruned) | exact (in-place) |
| `tests/test_facade.py` | CREATE (new) | test | request-response | `tests/test_facade.py` (self, exists) | exact (in-place) |
| `pyproject.toml` | VERIFY (no change needed) | config | — | `pyproject.toml:38-47,57-83` | exact (in-place) |
| `README.md` | MODIFY (docs) | doc | — | `README.md` (tracked, 429 lines) | role-match |
| `bench.py` | VERIFY (existing harness) | utility (benchmark) | batch | `bench.py` + `tests/test_bench.py` | role-match |

---

## Pattern Assignments

### `src/main.py` (controller, request-response + streaming)

**Analog:** `src/main.py` (806 lines, tracked)

**Headless sink class — replaces the retired terminal renderer** (lines 80-90):
```python
class _StdoutSink:
    """Headless frame sink: writes each rendered ASCII frame to stdout.

    Replaces the retired terminal renderer for CLI runs: frames leave as plain
    text with no terminal escape sequences, so the command stays usable when
    the output is piped, redirected, or captured.
    """

    def write_frame(self, frame_string: str) -> None:
        sys.stdout.write(frame_string + "\n")
        sys.stdout.flush()
```

**Duck-typed `run()` signature** (lines 350-362) — `sink: Any` is the decoupling point; the TUI
loop is gone. Copy this signature shape for any new consumer:
```python
def run(
    reader,
    renderer,
    sink: Any,
    clock: FrameClock,
    config: Config,
    audio: AudioPlayer | None = None,
    timeline: PlaybackTimeline | None = None,
    media_duration: float | None = None,
    video_aspect: float | None = None,
    first_frame: bytes | None = None,
    timestamp_stream: TimestampStream | None = None,
) -> int:
```

**Sink capability discovery via `getattr` chain** (lines 458-466 and 501-505) — never
`isinstance`; probe each optional capability independently:
```python
refresh_size = getattr(sink, "refresh_size", None)
output_size = getattr(sink, "output_size", None)
if refresh_size is not None and output_size is not None and refresh_size():
    new_width, new_height = output_size(video_aspect)
    ...
write_frame = getattr(sink, "write_frame", None)
if callable(write_frame):
    write_frame(ascii_frame)
elif callable(sink):
    sink(ascii_frame)
```

**Teardown restore via duck-typing** (lines 588-590):
```python
restore = getattr(sink, "restore", None)
if callable(restore):
    restore()
```

**Boundary error handling with exit-code contract** (lines 619-626, 777-791) — usage errors
exit 2, playback failures exit 1, never a traceback:
```python
except ValueError as exc:
    print(f"Error: {exc}", file=sys.stderr)
    return 2
...
except (
    FFmpegNotFoundError,
    FFmpegDecodeError,
    FileNotFoundError,
    FFplayNotFoundError,
    FFplayPlaybackError,
    ValueError,
) as exc:
    print(f"Error: {exc}", file=sys.stderr)
    return 2 if isinstance(exc, ValueError) else 1
```

**Lenient env parsing helpers** (lines 142-167) — `_env_bool`, `_env_float`, `_env_int`;
malformed values fall back to defaults rather than aborting. `config_from_args` (170-239)
layers precedence: CLI flag > env var > `Config` default.

**Headless default grid** (lines 93-107) — `_headless_output_size`: fixed 80 columns, rows
derived from `char_aspect / video_aspect`; mirrors retired terminal sizing math without a viewport.

### `src/__init__.py` (provider/facade, transform)

**Analog:** `src/__init__.py` (92 lines, tracked) — matches RESEARCH.md Pattern 1 verbatim.

**Facade structure** (lines 1-48): module docstring declaring the engine's scope, then
`from __future__ import annotations`, then explicit `from src.<module> import (...)` blocks —
**never** `from src import ...` inside submodules (cyclic-import pitfall, RESEARCH.md Pitfall 3).

**`__all__` grouping** (lines 50-92) — five comment-labelled groups: Renderer & Algorithms,
Configuration, Video & Audio Decoding Subprocesses, Timeline Timing & Sync, Pacing Selection &
Adaptation. 40 symbols exported.

**Verification hook:** `tests/test_facade.py:28-31` enforces the D-03 contract:
```python
def test_facade_exports_every_declared_symbol():
    """Every name in ``__all__`` is importable from ``src`` (D-03 contract)."""
    missing = [name for name in src.__all__ if not hasattr(src, name)]
    assert not missing, f"facade exports declared but absent: {missing}"
```

### `src/config.py` (config, CRUD)

**Analog:** `src/config.py` (76 lines, tracked)

**`status_rows` is already removed** — the dataclass (lines 29-66) carries only headless-relevant
fields (`chars`, `preset`, `fps`, `char_aspect`, `smoothing`, `enable_audio`, `enable_color`,
`debug`, `blocks`, `adaptive_quality`). No terminal viewport field remains.

**Strict `__post_init__` validation** (lines 68-76) — the strict counterpart to `main.py`'s
lenient env layer:
```python
def __post_init__(self) -> None:
    if not self.chars:
        raise ValueError("chars gradient must not be empty")
    if self.fps <= 0:
        raise ValueError("fps must be positive")
    if not 0.0 <= self.smoothing <= 1.0:
        raise ValueError("smoothing must be in [0, 1]")
    if self.char_aspect <= 0:
        raise ValueError("char_aspect must be positive")
```

**Preset table pattern** (lines 18-26) — `CHAR_PRESETS: dict[str, str]` with inline rationale
comments per entry; `DEFAULT_CHARS` referenced by the `"default"` key.

### `src/renderer.py` (service, transform — pure algorithm)

**Analog:** `src/renderer.py` (330 lines, tracked)

**Module isolation contract** (lines 1-9): "It knows nothing about FFmpeg, files, or terminals."
The only ANSI strings here are *render output* escape sequences (`_ANSI_COLOR` line 18,
`_ANSI_RESET` line 19) — not terminal control (cursor/resize/clear), which is what was pruned.

**Buffer-length validation before pixel indexing** (lines 165-174) — security control
(RESEARCH.md ASVS V5):
```python
if src_width <= 0 or src_height <= 0 or dst_width <= 0 or dst_height <= 0:
    raise ValueError("frame dimensions must be positive")
expected = src_width * src_height * 3
if len(frame) != expected:
    raise ValueError(
        f"RGB24 frame length {len(frame)} does not match "
        f"{src_width}x{src_height} ({expected})"
    )
```

**Zero-dependency planar rescaling** (lines 179-212) — `resize_rgb24_area`: contiguous
per-channel planes (`frame[0::3]`) for CPython fast-path `sum()`, rounded mean
`(2 * sum + n) // (2 * n)`. Per D-04, no Pillow/NumPy — do not introduce them.

**Hot-path memoization** (lines 31-46, 120-142) — `_char_table_cache` dict for 256-entry
gradient tables; `@lru_cache(maxsize=None)` on `_box_ranges`.

### `src/video.py` (service, streaming)

**Analog:** `src/video.py` (277 lines, tracked)

**Module-local exception taxonomy** (lines 18-23):
```python
class FFmpegNotFoundError(RuntimeError): ...
class FFmpegDecodeError(RuntimeError): ...
```

**Subprocess safety — explicit argv list, no shell** (lines 123-159):
```python
cmd = [
    self.ffmpeg,
    "-i", self.video_path,
    "-fps_mode", "passthrough",
    "-f", "rawvideo",
    "-pix_fmt", "rgb24",
    "-vf", f"scale={self.width}:{self.height}:flags=area",
    "-loglevel", "error",
    "-",
]
...
proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=stderr_file,
)
```
(`shell=False` is Popen's default and never overridden. FFmpeg's stderr goes to a
`tempfile.TemporaryFile`, not a pipe, to avoid a mid-decode pipe deadlock.)

**Fatal-vs-EOF classification** (lines 61-87) — `_FATAL_TERMINATION_MARKERS` tuple of
`(marker, reason)` pairs; `classify_decode_termination(log_tail) -> str | None` is
conservative-by-default (unrecognized log ⇒ clean EOF) and case-insensitive.

**Never-raises teardown with terminate→kill backstop** (lines 243-270) — `close()` swallows
`OSError`, degrades `terminate()` → `wait(2)` → `kill()` → `wait(2)`, always closes pipes in
`finally`. Runs from callers' `finally` blocks.

**Context-manager wrapper** (lines 272-277) — `__enter__`/`__exit__` delegating to
`open()`/`close()`.

### `src/audio.py` (service, event-driven)

**Analog:** `src/audio.py` (348 lines, tracked)

**Tri-state probe with graceful degradation** (lines 37-64) — `_probe_ffprobe` returns
`AudioStatus.UNKNOWN` (never raises) when ffprobe is missing or the probe fails; absence must
be *positively confirmed*, not inferred from failure:
```python
try:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0",
         video_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return AudioStatus.UNKNOWN
    return AudioStatus.CONFIRMED if result.stdout else AudioStatus.ABSENT
except (OSError, subprocess.SubprocessError):
    return AudioStatus.UNKNOWN
```

**Injectable time for deterministic tests** (lines 99-118) — `AudioPlayer(ffplay=None, now=None,
sleep_fn=None)`; tests inject `FakeTime.now`/`.sleep`. Mirror this in any new timed component.

**Daemon reader thread + lock-guarded state** (lines 167-177, 179-214) — stderr status lines
parsed in `threading.Thread(daemon=True)`; media position updated under `self._stats_lock`.

**`stop()` never raises** (lines 313-348) — same teardown doctrine as `video.py:close()`:
terminate → wait(2) → kill backstop, join stats thread with timeout, close stderr, all inside
`except OSError: pass`.

### `tests/test_facade.py` (test, request-response) — the NEW file

**Analog:** `tests/test_facade.py` (97 lines, tracked) — already exists; copy its structure for
any additional contract tests.

**Tracer-test pattern** (lines 14-42): import through the facade alone (`import src; from src
import ...`), assert `callable()` on key exports, then exercise one end-to-end synthetic frame
pipeline (`Config` → `resize_rgb24_area` → `render_frame`).

**Deletion-contract assertions** (lines 83-97) — how D-01 pruning is pinned by tests:
```python
def test_terminal_module_is_pruned_from_disk():
    """D-01: ``src/terminal.py`` is deleted, not archived."""
    assert not (REPO_ROOT / "src" / "terminal.py").exists()

def test_main_is_decoupled_from_terminal_renderer():
    """D-01: ``src/main.py`` has no TerminalRenderer import or reference."""
    assert "TerminalRenderer" not in MAIN_SOURCE
    assert "from src.terminal" not in MAIN_SOURCE
    assert "import src.terminal" not in MAIN_SOURCE

def test_facade_import_does_not_load_terminal_module():
    assert "src.terminal" not in sys.modules
```
(`MAIN_SOURCE = (REPO_ROOT / "src" / "main.py").read_text(...)` at lines 24-25.)

### `tests/test_playback.py` (test, request-response)

**Analog:** `tests/test_playback.py` (202 lines, tracked) — TUI assertions already pruned.
What remains is sink-protocol testing, not terminal-geometry testing.

**Duck-typed test double for the sink** (lines 43-70) — named `FakeTerminal` but implements
exactly the sink protocol (`output_size`, `refresh_size`, `clear`, `write_frame`, `restore`);
zero escape-sequence or cursor assertions:
```python
class FakeTerminal:
    def __init__(self, sizes=None, initial=(8, 8)):
        self.written = 0
        self.restored = False
        ...
    def write_frame(self, _frame_string):
        self.written += 1
    def restore(self):
        self.restored = True
```

**Deterministic clock injection** (lines 16-18, 77-78) — `_noop_sleep` passed into
`FrameClock(fps, sleep_fn=_noop_sleep)`; `fps=1000` keeps loops instantaneous.

### `tests/test_cleanup.py` (test, request-response)

**Analog:** `tests/test_cleanup.py` (301 lines, tracked) — guards `finally` blocks only.

**Hostile-teardown double** (lines 76-101) — `HostileProc` fails `poll`/`terminate`/`kill`/
`wait`/`close` every way a real process might; the assertion is that `stop()` still does not
raise and leaves the player disarmed (lines 104-115).

**Second-interrupt coverage** (lines 219-263) — `InterruptingAudio.wait_for_exit` raises
`KeyboardInterrupt` inside the `finally`; asserts `audio.stopped` and `terminal.restored`
still happen and the run still reports 0.

### `pyproject.toml` (config) — verify, do not modify

**Analog:** `pyproject.toml` (83 lines, tracked)

- Entrypoint intact (lines 38-47): `rgb-ascii = "src.main:main"` with rationale comment;
  `packages = ["src"]` required for flat-layout discovery (lines 43-47).
- Zero runtime deps (line 28): `dependencies = []` — D-02 guard; any added dependency violates it.
- Tool config (lines 49-83): pytest `pythonpath = ["."]`, mypy `files = ["src"]`,
  `python_version = "3.10"`, ruff `select = ["E4", "E7", "E9", "F"]` with a deliberate-narrowness
  rationale comment. Keep selection list unchanged; widen only in its own dedicated change.

### `README.md` / `bench.py` (doc / utility) — role-match only

Both tracked and present (429 / 475 lines). `bench.py` has its own test file `tests/test_bench.py`
(9 tests per RESEARCH.md). If plans touch either, match the existing zero-dependency,
stdlib-only style of the engine modules; no dedicated excerpt extraction needed.

---

## Shared Patterns

### S1. Subprocess Execution Safety
**Source:** `src/video.py:123-159` (primary), `src/audio.py:48-59, 138-161`
**Apply to:** every current or future subprocess invocation in the engine
```python
cmd = [self.ffmpeg, "-i", self.video_path, ...]   # explicit argv list
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr_file)
```
Never `shell=True`, never `os.system`, never string-formatted command lines. User-supplied
paths enter only as single argv elements.

### S2. Never-Raises Teardown
**Source:** `src/video.py:243-270` (`close()`), `src/audio.py:313-348` (`stop()`), `src/main.py:792-802` (`main` finally)
**Apply to:** all resource lifecycles
```python
try:
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=2)
        except subprocess.TimeoutExpired: proc.kill()
except OSError:
    pass
finally:
    # close streams
```
Doctrine (from `tests/test_cleanup.py` docstring): a `finally` that raises skips remaining
cleanup steps — the failure must be least-recoverable, so teardown swallows and continues.

### S3. Module-Local Exception Taxonomy
**Source:** `src/video.py:18-23`, `src/audio.py:19-24`
**Apply to:** every service module
Each module defines its own `RuntimeError` subclasses (`FFmpegNotFoundError`,
`FFmpegDecodeError`, `FFplayNotFoundError`, `FFplayPlaybackError`); `src/main.py:777-791`
catches the concrete tuple at the boundary. No generic `Exception` handling.

### S4. Duck-Typed Capability Protocol (sink)
**Source:** `src/main.py:458-466, 501-505, 588-590`
**Apply to:** any component consuming an optional collaborator
```python
write_frame = getattr(sink, "write_frame", None)
if callable(write_frame):
    write_frame(ascii_frame)
elif callable(sink):
    sink(ascii_frame)
```
Contract: `write_frame(str)` required-ish, callable fallback; `refresh_size`/`output_size`/
`clear`/`restore` all optional and individually probed. `None` discards output. This is what
lets `test_playback.py`/`test_cleanup.py` pass `FakeTerminal` doubles unchanged.

### S5. Strict Boundary / Lenient Environment Validation
**Source:** `src/config.py:68-76` (strict), `src/main.py:142-167, 170-239` (lenient)
**Apply to:** configuration ingestion
Direct construction raises `ValueError` on bad values; env-var reads degrade to defaults.
Cross-value impossibilities (e.g. `blocks` + no-color, `main.py:232-237`) are rejected at the
parsing boundary so they can never traceback inside the render loop.

### S6. Deterministic Time Injection
**Source:** `src/audio.py:99-118` (`now`/`sleep_fn`), `src/timing.py` (`FrameClock(sleep_fn=...)`)
**Apply to:** every timed/waiting component
Constructor-inject `now: Callable[[], float]` and `sleep_fn: Callable[[float], None]`;
tests inject `FakeTime` (`tests/test_cleanup.py:25-35`) or `_noop_sleep`.

### S7. Graceful Degradation Tri-State
**Source:** `src/audio.py:37-64`, `src/sync.py` `AudioStatus` enum
**Apply to:** all external-tool probes
Missing tool ⇒ UNKNOWN/fallback, never an abort: FFprobe missing ⇒ `UNKNOWN`; ffplay missing ⇒
silent playback warning (`main.py:703-714`); probe failure ⇒ fixed-FPS pacing (`main.py:656-666`).

### S8. Zero-Dependency Constraint Guard
**Source:** `pyproject.toml:28` (`dependencies = []`), `src/renderer.py:179-212`
**Apply to:** all engine code (D-02/D-04)
No Pillow, NumPy, OpenCV, Docker. New capability ⇒ stdlib or native FFmpeg subprocess.

---

## No Analog Found

| File | Role | Data Flow | Reason / Handling |
|------|------|-----------|-------------------|
| `src/terminal.py` | middleware (TUI) | event-driven | Deleted per D-01 and verified absent (`tests/test_facade.py:83-85` asserts non-existence). Only analog is git history: `git show 2a19dea^:src/terminal.py`. Plans must **not** restore it; the only legitimate reference is as a historical diff parent. |
| `tests/test_terminal.py` | test | request-response | Deleted per D-05, same handling as above (`git show 2a19dea^:tests/test_terminal.py`). |

No genuinely unmatched *new* work exists: the planned new file `tests/test_facade.py` already
exists and is tracked.

---

## Planner Guidance (Current-State Verification Checklist)

Because the transformation is committed, plan actions should be **verification-shaped**, keyed to
the files above:

1. **Facade contract (D-03):** `tests/test_facade.py:28-31` passes; `src/__init__.py:50-92`
   `__all__` matches actual exports; no submodule imports from `src` bare (Pitfall 3).
2. **Pruning contract (D-01/D-05):** `src/terminal.py` / `tests/test_terminal.py` absent from
   `git ls-files`; `src/config.py` has no `status_rows` (Pitfall 2); grep confirms no
   `src.terminal` reference anywhere in `src/` or `tests/`.
3. **Sink decoupling (D-01):** `src/main.py` contains no `TerminalRenderer`; sink protocol per
   S4; `pyproject.toml:41` entrypoint still `src.main:main`.
4. **Zero-dependency (D-02/D-04):** `dependencies = []`; no Pillow/NumPy imports;
   `resize_rgb24_area` still the pure-Python path.
5. **Health gates (MODERN-02/03):** full pytest suite green, `mypy` clean on `files = ["src"]`,
   `ruff` clean under `select = ["E4","E7","E9","F"]`; stale caches (`.mypy_cache`,
   `__pycache__` with terminal bytecode) cleared so pruned modules cannot resurrect via cache.

## Metadata

**Analog search scope:** `src/`, `tests/`, repo root (`pyproject.toml`, `README.md`, `bench.py`); git history for pruned modules.
**Files scanned:** 11 source modules + 19 test files enumerated; 9 read in full for excerpt extraction.
**Tracked-source gate:** every analog path verified tracked via `git ls-files` (non-empty for all; `src/terminal.py` and `tests/test_terminal.py` correctly absent).
**Pattern extraction date:** 2026-11-17
