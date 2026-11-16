<!-- GSD:project-start source:PROJECT.md -->

## Project

**RGB ASCII & Retro FX Studio**

A modern, high-performance browser-based retro visual effects and ASCII studio for images, videos, and live webcam streams. It delivers instant, GPU-accelerated client-side previews (ASCII, dithering, halftone, CRT/VHS, matrix rain, and color grading) alongside a Python FastAPI backend for high-fidelity FFmpeg-driven exports and processing. Built for digital artists, designers, and terminal enthusiasts seeking versatile retro graphics in a responsive studio interface.

**Core Value:** Instant, real-time retro visual transformations and high-fidelity media export across web and video formats, operating reliably at $0/month on free-tier cloud infrastructure.

### Constraints

- **Budget**: $0/month strict target across all cloud services (Cloudflare Pages free tier, Render free tier web service, Neon free tier).
- **Tech Stack (Frontend)**: Modern SPA (Vite / React / TypeScript / Tailwind CSS / WebGPU / Canvas) deployed to Cloudflare Pages.
- **Tech Stack (Backend)**: Python 3.10+ with FastAPI, Uvicorn, and FFmpeg deployed to Render via `render.yaml`.
- **UI Approval Gate**: All Stitch MCP visual designs must be reviewed and explicitly approved by the user before frontend code implementation begins.
- **Hermetic Testing**: Comprehensive unit and integration test coverage maintained throughout modernization and expansion.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python 3.10+ (tested across Python 3.10, 3.11, 3.12, 3.13) - Entire application and test suite (`src/`, `tests/`, `bench.py`).
- None. Standard library only; no C extensions, Rust modules, or compiled native extensions inside the Python package.

## Runtime

- Python 3 (standard CPython >= 3.10; currently active on Python 3.11.8 on Windows x64).
- `pip` / `setuptools>=61.0` (PEP 517 / PEP 621 build configuration via `pyproject.toml`).
- Lockfile: None (deliberately zero runtime dependencies; dev dependencies pinned loosely with minimum versions in `pyproject.toml`).

## Frameworks

- Standard Library Only - No third-party runtime frameworks. Subprocesses (`subprocess`), threading (`threading`), timing (`time.perf_counter`), math (`math`), terminal sizing (`shutil.get_terminal_size`), and I/O (`sys.stdout.buffer`, `sys.stderr`) are all from standard library.
- `pytest>=7.0` (active: pytest 9.0.2) - Test runner, parameterized testing, fixtures, and assertions (`tests/`).
- `pytest-asyncio`, `pytest-cov`, `anyio` - Detected in Python environment plugins.
- `setuptools>=61.0` - Build backend (`setuptools.build_meta`).
- `mypy>=1.0` - Static type checking configured in `pyproject.toml` (`[tool.mypy]` targeting `python_version = "3.10"` on `files = ["src"]`).
- `ruff>=0.1` - Fast linter configured in `pyproject.toml` (`[tool.ruff]` targeting `py310`, line length 100, linting rules `E4`, `E7`, `E9`, `F`).

## Key Dependencies

- None (`dependencies = []` in `pyproject.toml`).
- `ffmpeg` (required for video decoding): External executable on system `PATH`. Must support `-fps_mode passthrough`, `-f rawvideo`, `-pix_fmt rgb24`, and `-vf scale=W:H:flags=area`. Detected dynamically in `src/video.py` via `shutil.which("ffmpeg")`.
- `ffplay` (optional for audio playback): External executable on system `PATH`. Invoked in headless mode (`-vn -nodisp -autoexit -stats -loglevel warning`) in `src/audio.py` via `shutil.which("ffplay")`.
- `ffprobe` (optional for stream probing): External executable on system `PATH`. Probes container audio tracks (`-select_streams a`), video dimensions, FPS, and durations in `src/audio.py` and `src/sync.py`.
- `pytest>=7.0` - Test suite runner (`tests/`).
- `mypy>=1.0` - Type checking for `src/`.
- `ruff>=0.1` - Linting checks for code defects and syntax.

## Configuration

- `RGB_ASCII_NO_ADAPTIVE` - `1` to disable dynamic load shedding (`--no-adaptive` CLI equivalent).
- `RGB_ASCII_HALF_BLOCK` - `1` to enable experimental half-block mode (`\u2580` characters with foreground top pixel and background bottom pixel).
- `RGB_ASCII_NO_COLOR` - `1` to force monochrome output (grayscale ASCII glyphs without ANSI color escapes).
- `RGB_ASCII_NO_AUDIO` - `1` to disable audio playback even when FFplay and audio streams exist.
- `RGB_ASCII_SMOOTHING` - Float in `[0.0, 1.0]` specifying temporal alpha blend factor (default: `0.0` disabled).
- `RGB_ASCII_FPS` - Integer override for target playback frame rate (overrides video stream FPS).
- `RGB_ASCII_PRESET` - Predefined ASCII luminance ramp (`default`, `dense`, `simple`, `blocks`).
- `RGB_ASCII_CHARS` - Custom ASCII character gradient string (lowest luminance first, highest luminance last).
- `RGB_ASCII_DEBUG` - `1` to print timing diagnostics, dropped frames, audio status, and A/V drift stats to `sys.stderr`.
- `pyproject.toml` - Declarative metadata, console entry points (`rgb-ascii = "src.main:main"`), package layout (`packages = ["src"]`), tool settings for pytest, mypy, and ruff.
- `requirements.txt` - Documentation of external native dependency expectations (standard library only).
- `.github/workflows/ci.yml` - Multi-OS GitHub Actions workflow matrix (Ubuntu, Windows) across Python 3.10 and 3.13.

## Platform Requirements

- Python >= 3.10 on Windows, macOS, or Linux.
- FFmpeg and FFplay binaries installed and on system PATH (for manual full-pipeline verification; automated test suite uses mocks and synthetic buffers).
- CLI application runnable via `python -m src.main <video_path>` or console script `rgb-ascii <video_path>`.
- Any ANSI True Color (24-bit RGB) capable terminal emulator (Windows Terminal, iTerm2, Kitty, Alacritty, GNOME Terminal, xterm, etc.).

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- Lowercase snake_case across all Python modules (`src/adaptive.py`, `src/framesel.py`, `src/video.py`).
- Test files prefixed with `test_` matching functionality or subsystem (`tests/test_sync.py`, `tests/test_renderer.py`).
- PascalCase for all classes, exceptions, and protocols (`FrameClock`, `AudioPlayer`, `FFmpegNotFoundError`, `TimestampSource`).
- Dataclasses use PascalCase (`Config`, `TimingStats`, `DropStats`, `PlaybackTimeline`).
- Enums use PascalCase with uppercase enum members (`AudioStatus.CONFIRMED`, `AudioStatus.ABSENT`).
- snake_case for all public and private functions (`render_frame`, `sleep_until_deadline`, `char_table_for`).
- Internal/private helpers start with a single leading underscore (`_box_ranges`, `_find_ffmpeg`, `_decimal_str`).
- Module-level constants in uppercase snake_case (`DEFAULT_CHARS`, `CHAR_PRESETS`, `FLUSH_GRACE`, `MAX_UTILIZATION`).
- Local variables in concise, descriptive snake_case (`frame_budget`, `ascii_frame`, `work_start`).

## Code Style

- Tool: Ruff (configured via `[tool.ruff]` in `pyproject.toml`).
- Line length: 100 characters max (`line-length = 100`).
- Target Python version: `py310` (`target-version = "py310"`).
- Selected lint rules: `E4`, `E7`, `E9`, `F` (strict syntax, undefined names, unused imports, pycodestyle errors without stylistic nitpicking).
- Type checking: Mypy (configured via `[tool.mypy]` in `pyproject.toml`).

## Import Organization

- All intra-project imports use absolute package imports prefixed with `src.` (`from src.config import Config`, not `from .config import Config`).
- No wildcard imports (`from ... import *` is never used).

## Error Handling

- Custom exceptions inherit from `RuntimeError` for operational/environment failures:
- Validation errors raise standard `ValueError` with clear messages:
- Main execution loops wrap operations in robust `try...finally` blocks to guarantee restoration of terminal cursor, reset of ANSI states, and graceful shutdown of background subprocesses.
- EOF and SIGINT (Ctrl+C) are caught cleanly, exiting with status 0 rather than dumping unhandled tracebacks to user consoles.

## Logging

- No third-party logging frameworks. Diagnostic outputs write directly to `sys.stderr` when debug mode is enabled (`Config.debug` or `RGB_ASCII_DEBUG=1`).
- The standard output stream (`sys.stdout`) is reserved exclusively for raw ANSI frame presentation.
- Debug diagnostics are grouped into structured, aligned textual tables (`_report_stats`, `_report_frames`, `_report_audio`, `_report_sync` in `src/main.py`).

## Comments & Documentation

- Triple-double-quoted module-level docstrings explaining architectural intent, constraints, and mathematical guarantees (e.g. `src/timing.py`, `src/sync.py`, `src/framesel.py`).
- Methods with non-obvious algorithms (e.g. area averaging in `src/renderer.py`, clock rebasing in `src/timing.py`) include detailed explanatory docstrings.
- Inline comments focus on *why*, especially where subtle race conditions, pipe deadlocks, or FFmpeg quirks were resolved (e.g., explaining why stderr is buffered to a tempfile rather than an unread pipe).

## Function Design

- Complete type annotations across all function arguments and return types.
- Type unions use modern pipe syntax `str | None`, `int | float` enabled by `from __future__ import annotations`.
- Protocols used where duck-typing provides better testability without cyclic imports (e.g. `TimestampSource` in `src/timing.py`).
- Rendering and math calculations avoid allocations inside hot loops.
- `src/renderer.py` utilizes precalculated string lookup tables (`_decimal_str = tuple(str(i) for i in range(256))`) and memoized lookup tables (`_char_table_cache`) to avoid per-pixel formatting overhead.

## Module Design

- Each module owns a single distinct phase of the media/presentation lifecycle.
- Zero cyclic dependencies between modules.
- Standalone testability: modules like `RGBAsciiRenderer`, `FrameClock`, and `FrameSelector` can be instantiated and exercised with purely synthetic inputs without touching disk or starting subprocesses.

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI & Pipeline Orchestrator | Parses arguments/env, initializes components, drives main playback loop, cleans up resources | `src/main.py` |
| Runtime Configuration | Defines `Config` dataclass and character presets; validates options | `src/config.py` |
| Video Decoding | Spawns FFmpeg subprocess, requests RGB24 raw video pipe on stdout, handles errors | `src/video.py` |
| Audio Playback | Spawns FFplay subprocess in headless mode, tracks playback status and audio clock | `src/audio.py` |
| Playback Timeline & Sync | Manages shared master timeline, probed video/audio properties, and natural exit policy | `src/sync.py` |
| Frame Clock & Timing | Paces playback against absolute deadlines on monotonic clock or adopted media clock | `src/timing.py` |
| Frame Selection | Drains FFmpeg pipe without backpressure; drops stale frames when behind deadline | `src/framesel.py` |
| Temporal Smoothing | Exponential blend of consecutive displayed frames in RGB24 space to reduce flicker | `src/smoothing.py` |
| Adaptive Quality Controller | Monitors per-frame render work; sheds smoothing or color during sustained overruns | `src/adaptive.py` |
| ASCII & ANSI Renderer | Maps RGB24 pixels to luminance and ASCII characters; formats 24-bit True Color ANSI | `src/renderer.py` |
| Terminal Controller | Queries terminal size, manages viewport aspect ratio, writes buffered frames to stdout | `src/terminal.py` |

## Pattern Overview

- **Zero Third-Party Runtime Dependencies:** Leverages Python's standard library and OS subprocesses for streaming video/audio.
- **Pipelined Subprocesses via Uncompressed Pipes:** FFmpeg decodes directly into memory via raw RGB24 frames on standard output, eliminating intermediate disk storage.
- **Non-Accumulating Absolute Deadline Scheduling:** Frame deadlines are anchored to an absolute playback origin (`deadline = start + target_media_time(N)`) rather than relative sleep chains, preventing frame drift.
- **Drained Non-Blocking Frame Dropping:** The video decoder pipe is read continuously; frames that become stale due to render lateness are dropped immediately rather than queued or backpressured into FFmpeg.
- **Graceful Multi-Stage Quality Degradation:** If host processing capacity falls behind the frame budget, `QualityController` adaptively disables temporal smoothing, followed by ANSI color formatting, preserving frame pacing over visual fidelity.

## Layers

- Purpose: CLI interface, parameter validation, lifecycle management, and main loop coordination.
- Location: `src/main.py`
- Contains: `main()`, `run()`, `config_from_args()`, and diagnostic reporting routines.
- Depends on: All lower layers (`src.config`, `src.video`, `src.audio`, `src.sync`, `src.timing`, `src.framesel`, `src.smoothing`, `src.adaptive`, `src.renderer`, `src.terminal`).
- Purpose: Interface with system multimedia binaries (`ffmpeg`, `ffplay`, `ffprobe`).
- Location: `src/video.py`, `src/audio.py`
- Contains: `FFmpegFrameReader`, `AudioPlayer`, and stream status detectors.
- Depends on: External CLI executables, `src.sync`.
- Used by: `src/main.py`.
- Purpose: Pacing, clock tracking, and synchronization between independent audio and video streams.
- Location: `src/sync.py`, `src/timing.py`
- Contains: `PlaybackTimeline`, `FrameClock`, `TimestampStream`, and completion timeout algorithms.
- Used by: `src/main.py`, `src/framesel.py`.
- Purpose: Real-time lag recovery, frame skipping, exponential smoothing, and load adaptation.
- Location: `src/framesel.py`, `src/smoothing.py`, `src/adaptive.py`
- Contains: `FrameSelector`, `TemporalSmoother`, `QualityController`.
- Used by: `src/main.py`.
- Purpose: Translating raw pixel buffers into ANSI strings and writing to terminal viewport.
- Location: `src/renderer.py`, `src/terminal.py`
- Contains: `RGBAsciiRenderer`, `resize_rgb24_area`, `char_table_for`, `TerminalRenderer`.
- Used by: `src/main.py`, `bench.py`.

## Data Flow

### Primary Video Playback Flow

## Key Abstractions

- Pacing engine that schedules each frame at `playback_start + target_media_time(N)`.
- Handles switching between monotonic clock and FFplay's reported audio clock seamlessly with time rebasing.
- Unified observation recorder tracking video launch, audio launch, first frame, video EOF, audio exit, and max A/V drift.
- Real-time rate adapter. Keeps decoder pipe flowing, evaluating each frame against current clock to discard already-obsolete frames before rendering.
- Core graphics engine. Implements Rec. 601 luminance weighting (`0.299*R + 0.587*G + 0.114*B`), precomputed character lookup tables, area-averaging re-scaling, and half-block character rendering.

## Entry Points

- Name: `rgb-ascii`
- Definition: `pyproject.toml: [project.scripts] rgb-ascii = "src.main:main"`
- Entry function: `src/main.py:main()`
- Command: `python -m src.main <path_to_video>`
- Entry function: `src/main.py:main()` via `if __name__ == "__main__": main()`
- Command: `python bench.py [options]`
- Entry function: `bench.py:main()`

## Architectural Constraints

- **Python Standard Library Only:** No external pip packages permitted at runtime.
- **External Dependency Requirement:** Host system must have `ffmpeg` (and optionally `ffplay`/`ffprobe`) installed on `PATH`.
- **Single-Threaded Render Pipeline:** Video decoding and terminal rendering run on the main process thread; audio runs in a separate FFplay process, with a light daemon thread only reading FFplay's stderr stats.
- **Memory Boundedness:** No unbounded frame buffering. Raw frame reads are immediately rendered or dropped.

## Anti-Patterns

### Chained Sleep Delay (`time.sleep(1/fps)`)

### Backpressuring FFmpeg on Lag

### String-Blending Escape Codes

## Error Handling

- `FFmpegNotFoundError` / `FFplayNotFoundError`: Intercepted with helpful platform-specific installation instructions (links to official downloads and PATH configuration tips).
- Decode Termination Classification: `classify_decode_termination` in `src/video.py` analyzes stderr logs to distinguish benign EOF or recoverable decoder packet drops from fatal container corruptions (e.g., missing MOOV atom, partial files).
- Defensive Terminal Restoration: `src/main.py:run` wraps playback in `try...finally` to ensure the cursor is unhidden and ANSI attributes reset even on unexpected crashes or user interrupts.

## Cross-Cutting Concerns

- **Logging & Diagnostics:** Centralized under `Config.debug`, printed cleanly to `sys.stderr` without polluting standard output video stream.
- **Terminal Resize Handling:** `TerminalRenderer.refresh_size()` dynamically detects terminal window resizing, triggering automatic viewport recalculation and clean redraws without resetting media playback.
- **Platform Portability:** Handles OS-specific newline conventions, terminal escape compatibility (ANSI True Color), and Windows console behavior.

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.agents/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-fast` for a trivial task inline, with no subagents and no PLAN.md
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
