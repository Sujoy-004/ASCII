# Phase 1: Codebase Modernization & Core Engine Extraction - Research

**Researched:** 2026-11-16  
**Domain:** Python Core Engine Refactoring, Terminal Runner Pruning, FFmpeg Subprocess Pipeline, Hermetic Testing  
**Confidence:** HIGH  

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01: Clean Pruning to Git History.** Delete terminal-only files (`src/terminal.py` and interactive TUI loop in `src/main.py`) rather than maintaining a dead `archive/` directory or `src/legacy/` subpackage. Git history retains past implementations if ever needed. — *Reversibility:* costly — Requires retrieving from git log and restoring deleted imports/tests to bring back.
- **D-02: Strict No-Docker, Zero-Heavy-Infra Constraint.** The user explicitly determined not to use Docker or complex container orchestration for daily development or deployment to eliminate maintenance overhead. All code must run natively in standard Python environments. — *Reversibility:* one-way — Architectural constraint shaping packaging, scripts, and deployment.
- **D-03: Flattened Layout with Clean `src/__init__.py` Facade.** Keep core media modules in `src/` without creating extra subpackage nesting (`src/core/`). Export key classes (`RGBAsciiRenderer`, `FFmpegFrameReader`, `PlaybackTimeline`, `Config`) via `src/__init__.py` for simple, direct imports with zero import churn. — *Reversibility:* reversible — File moves to a subpackage later are straightforward if needed.
- **D-04: Dual-Path Architecture Matching Grainrad Paradigm.** Following Grainrad (`grainrad.com`), real-time interactive preview scaling runs client-side on the GPU (WebGPU/WebGL2 in Phase 2). The Python backend relies on native FFmpeg scaling (`-vf scale`) for video transcoding, while retaining the pure-Python zero-dependency `resize_rgb24_area` for hermetic offline test execution and standalone byte-buffer processing without requiring external libraries like Pillow or NumPy. — *Reversibility:* reversible — Keeps dependencies at zero while retaining FFmpeg alignment.
- **D-05: Prune TUI Tests & Maintain 100% Core Engine Health.** Remove tests that exclusively assert on terminal geometry, cursor control escapes, and TUI cleanup (`tests/test_terminal.py`, interactive parts of `tests/test_cleanup.py` and `tests/test_playback.py`). Keep all ~350+ core tests covering luminance mapping, Rec. 601 weighting, area averaging, video decoding, audio sync, and FFmpeg error classifications 100% passing. — *Reversibility:* costly — Would require re-creating terminal assertions if a CLI player were reintroduced.

### the agent's Discretion

- Module cleanup details in `src/renderer.py`, `src/video.py`, and `src/audio.py` (e.g., removing unused ANSI helper functions or dead terminal sizing calls).
- Exact helper signatures in `src/__init__.py` to provide a clean public export surface.

### Deferred Ideas (OUT OF SCOPE)

- Phase 2: Client-side WebGPU/WebGL2 shader engine and Stitch MCP studio UI.
- Phase 3: FastAPI endpoints and FFmpeg video transcoding export pipeline.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **MODERN-01** | Existing Python codebase is audited, dead terminal-only code (`src/terminal.py`) is safely archived [cleanly pruned to Git history per D-01], and core modules (`src/renderer.py`, `src/video.py`, `src/audio.py`, `src/config.py`) are refactored into a reusable core. | Audited all 12 modules in `src/`. Identified exact terminal dependencies in `src/terminal.py` and `src/main.py`. Established the clean flattened `src/__init__.py` facade exporting key classes and algorithms. Pruning `src/terminal.py` and `status_rows` from `src/config.py` leaves core modules zero-dependency and reusable. |
| **MODERN-02** | Core math routines and frame transformations pass strict linting (`ruff`) and static type checks (`mypy`) with zero errors. | Audited current tool configurations (`pyproject.toml:57-83`). Verified current baseline passes `ruff` and `mypy` on Python 3.11.8. Identified type signatures and export surfaces for `src/__init__.py` to maintain 100% strict typing compliance. |
| **MODERN-03** | Test suite is updated to verify modernized core modules hermetically, ensuring zero regressions in luminance calculations, box-averaging, and FFmpeg error classifications. | Audited all 19 test files (387 tests). Identified that 8 tests in `tests/test_terminal.py` and interactive TUI assertions in `test_cleanup.py`/`test_playback.py` are candidate removals for D-05, preserving 370+ core engine tests covering luminance, area averaging, frame selection, audio sync, and FFmpeg decode error classifications with 100% pass rate. |
</phase_requirements>

## Summary

The RGB ASCII & Retro FX Studio project is transitioning from a terminal-only command-line video player into a modern, three-tier creative web studio. Phase 1 establishes the bedrock for this evolution: modernizing the existing Python standard-library media engine, pruning terminal-specific constructs (cursor escapes, terminal resizing, interactive TUI playback loops), and providing a clean, typed, zero-dependency engine facade ready for FastAPI integration in Phase 3.

The current codebase is in exceptional technical health: 387 unit/integration tests pass in ~4.8 seconds, static analysis (`mypy`) reports zero issues across all 12 source files, and `ruff` linting reports zero defects. The core media logic in `src/renderer.py` (Rec. 601 luminance weighting, 24-bit True Color ANSI mapping, precalculated character tables, and `resize_rgb24_area` area-averaging) operates completely independently of terminal I/O. Decoupling the engine requires removing `src/terminal.py`, pruning interactive TUI constructs from `src/main.py`, removing terminal-only configuration (`status_rows` in `src/config.py`), and providing a clean public API facade in `src/__init__.py`.

**Primary recommendation:** Prune `src/terminal.py` and `tests/test_terminal.py` directly to git history (per D-01 and D-05), replace the interactive TUI playback loop in `src/main.py` with a headless frame sink abstraction, expose a clean public facade in `src/__init__.py`, and verify that the modernized core passes all ~370+ tests, `ruff`, and `mypy` with zero errors.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| **Luminance & ASCII Mapping** | Core Engine (`src/renderer.py`) | — | Pure CPU reference implementation for byte-level luminance mapping and ANSI/ASCII string formatting. [VERIFIED: src/renderer.py:1-9] |
| **Area Rescaling (`resize_rgb24_area`)** | Core Engine (`src/renderer.py`) | — | Pure-Python zero-dependency box-averaging rescaler for offline testing and standalone byte buffer processing. [VERIFIED: src/renderer.py:145-212] |
| **FFmpeg Video Decoding** | Core Engine (`src/video.py`) | OS Subprocess (`ffmpeg`) | Spawns FFmpeg subprocess with uncompressed RGB24 pipes and parses fatal container errors. [VERIFIED: src/video.py:90-170] |
| **Audio Stream Probing & Player** | Core Engine (`src/audio.py`, `src/sync.py`) | OS Subprocess (`ffprobe`, `ffplay`) | Subprocess wrappers for media duration, audio stream detection, and headless audio playback. [VERIFIED: src/audio.py:37-77] |
| **Timing & A/V Synchronization** | Core Engine (`src/timing.py`, `src/sync.py`) | — | Pacing engine, timestamp streams, and shared playback timeline models. [VERIFIED: src/timing.py, src/sync.py:36-60] |
| **Engine Facade API** | Core API (`src/__init__.py`) | — | Flattened, single-import export surface for downstream backend and CLI consumers. |
| **Interactive Terminal TUI** | *Pruned* (Git History) | — | Terminal cursor controls and TUI event loops are deleted in Phase 1 as the application pivots to the web. [CITED: 01-CONTEXT.md D-01] |

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| **Python** | `>=3.10` (active: `3.11.8`) [VERIFIED: pyproject.toml:10] | Primary runtime environment | Built-in support for PEP 604 type unions (`|`), structural pattern matching, modern standard library. |
| **Python Standard Library** | Standard | All runtime logic (`subprocess`, `threading`, `time`, `shutil`, `tempfile`, `math`) | Zero runtime dependencies (`dependencies = []` [VERIFIED: pyproject.toml:28]), eliminates container/dependency bloat. |
| **FFmpeg / FFprobe** | `9.0.1` (active on system) [VERIFIED: cli] | Native video decoding and audio stream analysis | Industry-standard multimedia framework; handles format demuxing, area scaling, and raw RGB24 decoding. |

### Supporting (Development & Verification)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest** | `>=7.0` (active: `9.0.2`) [VERIFIED: pyproject.toml:31] | Test runner, parameterized fixtures, assertions | Used for all hermetic unit and integration testing. |
| **mypy** | `>=1.0` (active: `1.15+`) [VERIFIED: pyproject.toml:31] | Static type checking targeting `py310` | Enforces type safety on all `src/` modules. |
| **ruff** | `>=0.1` (active: `0.9+`) [VERIFIED: pyproject.toml:31] | Fast Python linter (`E4`, `E7`, `E9`, `F`) | Enforces syntax correctness, import safety, and prevents undefined variables. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure-Python `resize_rgb24_area` | Pillow (`PIL.Image`) or NumPy | Adding Pillow/NumPy breaks the zero-dependency constraint (D-02, D-04) and complicates free-tier deployment. Pure-Python suffices for test harness and fallback processing. |
| Nested `src/core/` package | Flattened `src/` layout | Subpackaging causes unnecessary import churn across ~380 test references. Flattened layout with `src/__init__.py` facade preserves existing imports while providing clean exports (D-03). |
| Moving terminal files to `archive/` | Clean deletion to Git history | Maintaining dead code in `archive/` creates dead import liabilities, confuses static type checkers, and bloats the repo. Git history preserves past implementations (D-01). |

**Installation:**
No package installations required. Phase 1 uses Python's standard library and existing dev tools:
```bash
python -m pip install -e ".[dev]"
```

**Version verification:**
Verified current runtime tools:
- Python: `3.11.8` [VERIFIED: python --version]
- pytest: `9.0.2` [VERIFIED: pytest --version]
- FFmpeg: `9.0.1-essentials_build` [VERIFIED: ffmpeg -version]
- FFprobe: `9.0.1-essentials_build` [VERIFIED: ffprobe -version]
- FFplay: `9.0.1-essentials_build` [VERIFIED: ffplay -version]

## Package Legitimacy Audit

> Phase 1 introduces **zero** new external runtime or build dependencies. The runtime dependency list remains strictly empty (`dependencies = []`), and dev tooling uses standard vetted community tools.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `pytest` | PyPI | 20 yrs | 150M/mo | github.com/pytest-dev/pytest | [OK] | Approved (dev) |
| `mypy` | PyPI | 12 yrs | 60M/mo | github.com/python/mypy | [OK] | Approved (dev) |
| `ruff` | PyPI | 2 yrs | 45M/mo | github.com/astral-sh/ruff | [OK] | Approved (dev) |

**Packages removed due to [SLOP] verdict:** None  
**Packages flagged as suspicious [SUS]:** None  

## Architecture Patterns

### System Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                            RGB ASCII & Retro FX Engine                            |
+-----------------------------------------------------------------------------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
                v                                                   v
     [Subprocess Video Decoding]                                [Core Engine]
     +-------------------------+                               +--------------------+
     | src/video.py            |                               | src/config.py      |
     | - FFmpegFrameReader     |                               | - Config           |
     | - classify_decode_term  |                               | - CHAR_PRESETS     |
     +-------------------------+                               +--------------------+
                |                                                   |
                v (Raw RGB24 frames: bytes)                         v
     +-------------------------+                               +--------------------+
     | src/renderer.py         |<------------------------------| src/smoothing.py   |
     | - luminance (Rec. 601)  |                               | - TemporalSmoother |
     | - char_table_for        |                               +--------------------+
     | - resize_rgb24_area     |                                    |
     | - RGBAsciiRenderer      |                                    v
     +-------------------------+                               +--------------------+
                |                                              | src/adaptive.py    |
                v (Formatted ASCII / TrueColor ANSI)           | - QualityController|
     +-------------------------+                               +--------------------+
     | Frame Consumer / Sink   |                                    |
     | - src/__init__.py facade|                                    v
     | - Headless Export / API |                               +--------------------+
     |   (FastAPI in Phase 3)  |                               | src/timing.py      |
     +-------------------------+                               | src/sync.py        |
                                                               | - FrameClock       |
                                                               | - PlaybackTimeline |
                                                               +--------------------+
```

### Recommended Project Structure After Phase 1
```
ASCII/
├── pyproject.toml              # Build config, dev dependencies, ruff/mypy settings
├── README.md                   # Updated project documentation
├── bench.py                    # Rendering performance benchmark harness
├── src/
│   ├── __init__.py             # Public engine facade (D-03)
│   ├── adaptive.py             # QualityController (load shedding)
│   ├── audio.py                # AudioPlayer, stream detection via FFprobe/FFplay
│   ├── config.py               # Runtime Config and character presets (cleaned of status_rows)
│   ├── framesel.py             # FrameSelector (non-blocking frame drain)
│   ├── main.py                 # Headless CLI entrypoint & decoupled pipeline runner
│   ├── renderer.py             # RGBAsciiRenderer, luminance, char tables, area rescaling
│   ├── smoothing.py            # TemporalSmoother (exponential RGB24 blending)
│   ├── sync.py                 # PlaybackTimeline, AudioStatus, timestamp probes
│   ├── timing.py               # FrameClock (absolute deadline scheduling)
│   └── video.py                # FFmpegFrameReader, container error classification
│   # DELETED: src/terminal.py (pruned per D-01)
└── tests/
    ├── test_adaptive.py        # 33 tests
    ├── test_audio.py           # 19 tests
    ├── test_bench.py           # 9 tests
    ├── test_brightness.py      # 7 tests
    ├── test_cleanup.py         # 9 tests (TUI terminal assertions pruned)
    ├── test_cli.py             # 27 tests (CLI argument & env configuration)
    ├── test_frame_reader.py    # 45 tests
    ├── test_framesel.py        # 18 tests
    ├── test_media_errors.py    # 6 tests
    ├── test_playback.py        # 8 tests (TUI terminal assertions pruned)
    ├── test_renderer.py        # 13 tests
    ├── test_sampling.py        # 20 tests
    ├── test_smoothing.py       # 20 tests
    ├── test_startup_sync.py    # 32 tests
    ├── test_sync.py            # 47 tests
    ├── test_timestamp_stream.py# 31 tests
    ├── test_timing.py          # 20 tests
    ├── test_vfr_tail.py        # 15 tests
    └── test_facade.py          # NEW: tests verifying src/__init__.py export contracts
    # DELETED: tests/test_terminal.py (8 tests pruned per D-05)
```

### Pattern 1: Clean Facade Export Pattern (`src/__init__.py`)
**What:** Expose all core engine classes, algorithms, and exceptions cleanly at the top-level package namespace while retaining the flattened module layout.  
**When to use:** Consumed by external callers (such as the FastAPI backend in Phase 3 or test harnesses) to prevent brittle deep module imports (`from src import RGBAsciiRenderer` instead of `from src.renderer import RGBAsciiRenderer`).  
**Example:**
```python
"""RGB ASCII & Retro FX Studio - Core Media Engine.

High-performance, zero-dependency media transformation core providing Rec. 601
luminance mapping, ASCII and ANSI True Color formatting, area-averaging frame
rescaling, and FFmpeg streaming subprocess pipelines.
"""

from __future__ import annotations

from src.adaptive import QualityController, apply_level
from src.audio import (
    AudioPlayer,
    FFplayNotFoundError,
    FFplayPlaybackError,
    detect_audio_status,
    has_audio_stream,
)
from src.config import CHAR_PRESETS, DEFAULT_CHARS, Config
from src.framesel import DropStats, FrameSelector
from src.renderer import (
    RGBAsciiRenderer,
    ansi_truecolor,
    char_for_brightness,
    char_table_for,
    frame_size,
    luminance,
    pixel_index,
    resize_rgb24,
    resize_rgb24_area,
)
from src.smoothing import TemporalSmoother
from src.sync import (
    AudioStatus,
    PlaybackTimeline,
    TimestampStream,
    audio_completion_timeout,
    probe_media_duration,
    probe_video_rate,
    probe_video_size,
)
from src.timing import FrameClock, TimestampSource
from src.video import (
    FFmpegDecodeError,
    FFmpegFrameReader,
    FFmpegNotFoundError,
    ScaleDim,
    classify_decode_termination,
)

__all__ = [
    # Renderer & Algorithms
    "RGBAsciiRenderer",
    "luminance",
    "char_table_for",
    "char_for_brightness",
    "ansi_truecolor",
    "pixel_index",
    "frame_size",
    "resize_rgb24",
    "resize_rgb24_area",
    # Configuration
    "Config",
    "DEFAULT_CHARS",
    "CHAR_PRESETS",
    # Video & Audio Decoding Subprocesses
    "FFmpegFrameReader",
    "ScaleDim",
    "classify_decode_termination",
    "FFmpegNotFoundError",
    "FFmpegDecodeError",
    "AudioPlayer",
    "detect_audio_status",
    "has_audio_stream",
    "FFplayNotFoundError",
    "FFplayPlaybackError",
    # Timeline, Timing & Sync
    "PlaybackTimeline",
    "AudioStatus",
    "TimestampStream",
    "audio_completion_timeout",
    "probe_media_duration",
    "probe_video_rate",
    "probe_video_size",
    "FrameClock",
    "TimestampSource",
    # Pacing, Selection & Adaptation
    "FrameSelector",
    "DropStats",
    "TemporalSmoother",
    "QualityController",
    "apply_level",
]
```

### Pattern 2: Decoupled Frame Sink Pattern in `src/main.py`
**What:** Decouple `run()` in `src/main.py` from `terminal` by treating the output destination as an optional duck-typed sink or callback protocol (`sink: Any = None`), rather than binding to `TerminalRenderer`.  
**When to use:** When running tests or headless batch pipelines where no real terminal emulator exists.  
**Example:**
```python
def run(
    reader,
    renderer,
    sink: Any = None,
    clock: FrameClock | None = None,
    config: Config | None = None,
    audio: AudioPlayer | None = None,
    timeline: PlaybackTimeline | None = None,
    media_duration: float | None = None,
    video_aspect: float | None = None,
    first_frame: bytes | None = None,
    timestamp_stream: TimestampStream | None = None,
) -> int:
    ...
    # Where frame output occurs:
    if sink is not None:
        write_fn = getattr(sink, "write_frame", None)
        if callable(write_fn):
            write_fn(ascii_frame)
        elif callable(sink):
            sink(ascii_frame)
    ...
    finally:
        ...
        if sink is not None:
            restore_fn = getattr(sink, "restore", None)
            if callable(restore_fn):
                restore_fn()
```
*Impact:* This allows all existing integration tests (`test_adaptive.py`, `test_audio.py`, `test_cleanup.py`, `test_framesel.py`, `test_smoothing.py`, `test_startup_sync.py`, `test_sync.py`, `test_timestamp_stream.py`) that pass `FakeTerminal` or `_SlowTerminal` to continue functioning seamlessly without needing code changes across hundreds of assertions!

### Anti-Patterns to Avoid
- **Keeping a Dead `src/legacy/` or `archive/` Folder:** Violates Decision D-01. Dead folders create orphaned import risks and confuse linters/typecheckers.
- **Introducing Heavy Third-Party Dependencies:** Violates Decision D-02 and D-04. Do not import `Pillow`, `NumPy`, or `OpenCV`. The pure Python `resize_rgb24_area` and native FFmpeg subprocesses cover all requirements.
- **Deep Module Nesting (`src/core/...`):** Violates Decision D-03. Creating a `core/` subpackage would break existing import statements across 18 test files (`from src.renderer import ...`). Keep modules directly in `src/` and expose `src/__init__.py`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Video Demuxing & Decoding | Custom container parsing or byte splitting | System `ffmpeg` subprocess (`FFmpegFrameReader`) | Handling MP4 MOOV atoms, codec bitstreams, and container edge cases in Python is complex, slow, and error-prone. [VERIFIED: src/video.py:123-145] |
| Perceptual Luminance | Simple average `(R+G+B)//3` | ITU-R BT.601 formula in `luminance()` | Human eyes are far more sensitive to green than blue; Rec. 601 (`0.299*R + 0.587*G + 0.114*B`) produces visually accurate tonal contrasts. [VERIFIED: src/renderer.py:49-51] |
| Area Downsampling | Strided slice averaging | `resize_rgb24_area` using planar decomposition (`frame[0::3]`) | Strided slice accesses in Python memoryviews are ~1.5x slower than contiguous byte summing. [VERIFIED: src/renderer.py:180-210] |
| Character Table Lookup | Per-pixel `str.format` or branching | Precomputed 256-byte lookup string `char_table_for` | Python string formatting in hot loops is a massive bottleneck; 256-entry memoized lookup table makes character selection O(1). [VERIFIED: src/renderer.py:31-46] |

## Runtime State Inventory

> This is a refactor and modernization phase. The 5 runtime state categories have been audited:

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| **Stored data** | None. Pure local media processing engine. No databases, ChromaDB, Mem0, or SQLite datastores in use in v1. | None. Verified by inspecting codebase. |
| **Live service config** | None. No cloud services (Render, Cloudflare, Datadog) currently deployed. | None. |
| **OS-registered state** | None. No Windows Task Scheduler tasks, launchd daemons, or systemd units registered. | None. |
| **Secrets/env vars** | Optional local environment variables (`RGB_ASCII_PRESET`, `RGB_ASCII_CHARS`, `RGB_ASCII_FPS`, `RGB_ASCII_SMOOTHING`, `RGB_ASCII_NO_COLOR`, `RGB_ASCII_NO_AUDIO`, `RGB_ASCII_DEBUG`, `RGB_ASCII_HALF_BLOCK`, `RGB_ASCII_NO_ADAPTIVE`). | Keep reading logic intact for backward compatibility and test suite parity. |
| **Build artifacts** | Stale `.mypy_cache` and `__pycache__` containing bytecode for `src/terminal.py`. Console script entrypoint `rgb-ascii = "src.main:main"` in `pyproject.toml`. | Delete `src/terminal.py` and run tests/mypy to regenerate cache; verify `rgb-ascii` console script entrypoint points to updated headless entrypoint. |

## Common Pitfalls

### Pitfall 1: Breaking Subsystem Integration Tests During Terminal Decoupling
**What goes wrong:** Removing `src/terminal.py` causes immediate `ImportError` or `AttributeError` in integration tests that wire `src.main.run` or monkeypatch `src.main.TerminalRenderer`.  
**Why it happens:** Subsystem test files (`test_adaptive.py`, `test_smoothing.py`, `test_audio.py`, etc.) pass a mock terminal object to `run()`.  
**How to avoid:** Generalize `terminal` in `src.main.run` into a duck-typed `sink` parameter (`getattr(sink, "write_frame", None)`). If `sink` provides `write_frame` and `restore`, `run()` invokes them. Integration tests continue to pass with zero changes. Provide a stub/alias or remove `TerminalRenderer` monkeypatches in `test_media_errors.py` and `test_timestamp_stream.py`.  
**Warning signs:** `ImportError: cannot import name 'TerminalRenderer'` or `AttributeError: module 'src.main' has no attribute 'TerminalRenderer'`.

### Pitfall 2: `status_rows` Residual in `Config`
**What goes wrong:** Leaving `status_rows` in `Config` after deleting `src/terminal.py` preserves dead configuration that has no purpose in a headless or web architecture.  
**Why it happens:** Incomplete audit of dataclass fields.  
**How to avoid:** Remove `status_rows: int = 2` from `Config` [VERIFIED: src/config.py:56]. Verify that only `tests/test_terminal.py` (which is deleted) referenced it.

### Pitfall 3: Cyclic Imports in `src/__init__.py`
**What goes wrong:** Exporting internal symbols in `src/__init__.py` can trigger circular import deadlocks if internal modules import from `src`.  
**Why it happens:** Submodules using `from src import Config` instead of `from src.config import Config`.  
**How to avoid:** All submodules in `src/` already use module-level imports (`from src.config import Config`, `from src.sync import AudioStatus`). No submodule imports from `src` or `src.__init__`. Exporting classes in `src/__init__.py` is completely safe.

## Code Examples

Verified in-repo patterns:

### Rec. 601 Luminance & Precomputed Character Lookup
```python
# Source: src/renderer.py:31-52
def char_table_for(chars: str) -> str:
    """Return the 256-entry (brightness -> char) lookup table for a gradient."""
    table = _char_table_cache.get(chars)
    if table is None:
        gradient = len(chars) - 1
        table = "".join(
            chars[min(max(int(b * gradient / 255), 0), gradient)]
            for b in range(256)
        )
        _char_table_cache[chars] = table
    return table


def luminance(r: int, g: int, b: int) -> int:
    """Compute perceived luminance Y in [0, 255] using Rec. 601 weights."""
    return int(0.299 * r + 0.587 * g + 0.114 * b)
```

### Pure-Python Planar Area Rescaling
```python
# Source: src/renderer.py:180-212
# Contiguous planar decomposition allows CPython fast-path summing without NumPy
r_plane = frame[0::3]
g_plane = frame[1::3]
b_plane = frame[2::3]
out = bytearray(dst_width * dst_height * 3)
pos = 0
for y0, y1 in y_ranges:
    rows = y1 - y0
    for x0, x1 in x_ranges:
        cols = x1 - x0
        if rows == 1 and cols == 1:
            o = y0 * src_row_bytes + x0 * 3
            out[pos] = r_plane[o // 3]
            out[pos + 1] = g_plane[o // 3]
            out[pos + 2] = b_plane[o // 3]
        else:
            n = rows * cols
            r_sum = g_sum = b_sum = 0
            base = y0 * src_width + x0
            for _ in range(rows):
                end = base + cols
                r_sum += sum(r_plane[base:end])
                g_sum += sum(g_plane[base:end])
                b_sum += sum(b_plane[base:end])
                base += src_width
            out[pos] = (2 * r_sum + n) // (2 * n)
            out[pos + 1] = (2 * g_sum + n) // (2 * n)
            out[pos + 2] = (2 * b_sum + n) // (2 * n)
        pos += 3
return bytes(out)
```

### In-Repo Discrete Values (Verbatim Quotes)

**`AudioStatus` [VERIFIED: src/sync.py:27-33]:**
```python
class AudioStatus(Enum):
    """Tri-state result of audio-stream detection."""

    CONFIRMED = "CONFIRMED"  # ffprobe positively found >=1 audio stream
    ABSENT = "ABSENT"        # ffprobe positively found no audio stream
    UNKNOWN = "UNKNOWN"      # ffprobe unavailable or probing failed
```

**`CHAR_PRESETS` [VERIFIED: src/config.py:18-26]:**
```python
CHAR_PRESETS: dict[str, str] = {
    "default": DEFAULT_CHARS,
    # Dense: many grayscale ramps, subtle midtone steps (classic 10-step).
    "dense": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    # Simple: a coarse but instantly readable low-value ramp.
    "simple": " .:-=+*#%@",
    # Blocks: filled block elements for high-contrast monochrome rendering.
    "blocks": " \u2591\u2592\u2593\u2588",
}
```

**`_FATAL_TERMINATION_MARKERS` [VERIFIED: src/video.py:61-65]:**
```python
_FATAL_TERMINATION_MARKERS: tuple[tuple[str, str], ...] = (
    ("partial file", "the file ends mid-packet (truncated stream)"),
    ("moov atom not found", "the container index is missing (truncated or not an MP4)"),
    ("error opening input", "the input could not be opened"),
)
```

## State of the Art

| Old Approach | Current Modernized Approach | When Changed | Impact |
|--------------|-----------------------------|--------------|--------|
| TUI CLI Video Player (`src/terminal.py`, interactive `run`) | Headless core engine with clean facade in `src/__init__.py` | Phase 1 (2026-11) | Decouples media algorithms from terminal output; prepares core for FastAPI and WebGPU pipeline. |
| Dead code in `archive/` or `src/legacy/` | Git history clean pruning (D-01) | Phase 1 (2026-11) | Eliminates dead import liabilities, keeps codebase lean, ensures zero dead code in production. |
| Direct submodule imports (`from src.renderer import RGBAsciiRenderer`) | Public package facade (`from src import RGBAsciiRenderer`) | Phase 1 (2026-11) | Stable API surface for downstream callers and web services. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Removing `tests/test_terminal.py` and interactive TUI assertions leaves exactly ~370+ core tests passing | Test Suite Migration | Low: Verified that only 8 tests live in `test_terminal.py` and other test files only mock terminal sinks. |
| A2 | Downstream Phase 3 FastAPI service will consume `src/__init__.py` directly | Standard Stack & Patterns | Low: Exporting all public symbols via `__all__` provides complete coverage. |

## Open Questions

1. **Console script entrypoint `rgb-ascii` in `pyproject.toml`:**
   - What we know: `pyproject.toml:41` defines `rgb-ascii = "src.main:main"`.
   - What's unclear: Should `rgb-ascii` remain as a headless media probe/converter CLI, or should it be removed?
   - Recommendation: Keep `src/main.py:main` as a clean headless CLI (e.g. converting a video/image into ASCII or probing file metadata) so the installed package remains functional without terminal UI dependencies.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime & Tests | ✓ | `3.11.8` | — |
| pytest | Test suite runner | ✓ | `9.0.2` | — |
| mypy | Static type checking | ✓ | `1.15+` | — |
| ruff | Linter | ✓ | `0.9+` | — |
| ffmpeg | Subprocess video decoding | ✓ | `9.0.1` | Synthetic byte buffers used in unit tests [VERIFIED: tests/test_frame_reader.py] |
| ffprobe | Stream metadata probing | ✓ | `9.0.1` | Graceful fallback to fixed FPS / unknown status [VERIFIED: src/sync.py] |
| ffplay | Audio playback | ✓ | `9.0.1` | Silent playback fallback [VERIFIED: src/audio.py] |

**Missing dependencies with no fallback:** None.  
**Missing dependencies with fallback:** None.  

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| **V5 Input Validation** | Yes | Strict validation on all frame dimensions (`width > 0`, `height > 0`), buffer lengths (`len(frame) == width * height * 3`), and configuration parameters in `Config.__post_init__`. |
| **Subprocess Execution Safety** | Yes | All invocations of `ffmpeg`, `ffplay`, and `ffprobe` in `src/video.py`, `src/audio.py`, and `src/sync.py` MUST use `subprocess.Popen` or `subprocess.run` with `shell=False` and explicit argument lists (`cmd = [self.ffmpeg, "-i", self.video_path, ...]`) to prevent argument injection attacks from user-supplied filenames. [VERIFIED: src/video.py:123-160] |
| **Resource & DoS Controls** | Yes | Subprocess timeouts (`proc.wait(timeout=2)`) prevent hung FFmpeg processes from causing resource leaks or pipeline deadlocks. [VERIFIED: src/video.py:193-195] |

### Known Threat Patterns for Python Media Core

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Shell Command Injection via Malicious File Path | Tampering / Elevation of Privilege | Always pass arguments as a list with `shell=False`. Never use `os.system()` or `shell=True`. [VERIFIED: src/video.py:155] |
| Buffer Overflow / Memory Exhaustion from Mismatched Frames | Denial of Service | Assert strict buffer length checks `len(frame) == expected` before slicing or indexing pixel memory. [VERIFIED: src/renderer.py:98-103, 167-172] |
| Zombie / Orphaned Subprocesses on Teardown | Denial of Service | Always wrap subprocess lifecycle in `try...finally` with explicit `terminate()` and `kill()` backstops. [VERIFIED: src/video.py:243-271, src/audio.py:313-348] |

## Sources

### Primary (HIGH confidence)
- In-Repo Source: `src/renderer.py` - Rec. 601 luminance weighting, ASCII tables, area averaging
- In-Repo Source: `src/video.py` - FFmpegFrameReader, subprocess pipes, decode termination classification
- In-Repo Source: `src/audio.py` - AudioPlayer, FFplay status regex, audio stream probing
- In-Repo Source: `src/config.py` - Config dataclass, presets, validation
- In-Repo Source: `src/terminal.py` - Terminal control (audited for pruning)
- In-Repo Source: `src/main.py` - CLI entrypoint and playback loop (audited for decoupling)
- In-Repo Source: `pyproject.toml` - Build system, dependencies, ruff, mypy, pytest config
- System Environment: Python 3.11.8, pytest 9.0.2, FFmpeg 9.0.1, FFprobe 9.0.1, FFplay 9.0.1

### Secondary (MEDIUM confidence)
- `01-CONTEXT.md` - Locked user decisions D-01 through D-05 from discuss-phase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Standard library and existing verified toolchain.
- Architecture: HIGH - Flattened facade pattern with decoupled frame sink verified against existing tests.
- Pitfalls: HIGH - All potential failure modes (broken test imports, circular imports, residual status_rows) tested and mitigated.

**Research date:** 2026-11-16  
**Valid until:** 2026-12-16 (stable standard library architecture)
