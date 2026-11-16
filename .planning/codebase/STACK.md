---
last_mapped_commit: a55586b3cdf529951d93b522083233d43fa80a2e
last_mapped_at: 2026-11-16
---
# Technology Stack

**Analysis Date:** 2026-11-16

## Languages

**Primary:**
- Python 3.10+ (tested across Python 3.10, 3.11, 3.12, 3.13) - Entire application and test suite (`src/`, `tests/`, `bench.py`).

**Secondary:**
- None. Standard library only; no C extensions, Rust modules, or compiled native extensions inside the Python package.

## Runtime

**Environment:**
- Python 3 (standard CPython >= 3.10; currently active on Python 3.11.8 on Windows x64).

**Package Manager:**
- `pip` / `setuptools>=61.0` (PEP 517 / PEP 621 build configuration via `pyproject.toml`).
- Lockfile: None (deliberately zero runtime dependencies; dev dependencies pinned loosely with minimum versions in `pyproject.toml`).

## Frameworks

**Core:**
- Standard Library Only - No third-party runtime frameworks. Subprocesses (`subprocess`), threading (`threading`), timing (`time.perf_counter`), math (`math`), terminal sizing (`shutil.get_terminal_size`), and I/O (`sys.stdout.buffer`, `sys.stderr`) are all from standard library.

**Testing:**
- `pytest>=7.0` (active: pytest 9.0.2) - Test runner, parameterized testing, fixtures, and assertions (`tests/`).
- `pytest-asyncio`, `pytest-cov`, `anyio` - Detected in Python environment plugins.

**Build/Dev & Quality Tools:**
- `setuptools>=61.0` - Build backend (`setuptools.build_meta`).
- `mypy>=1.0` - Static type checking configured in `pyproject.toml` (`[tool.mypy]` targeting `python_version = "3.10"` on `files = ["src"]`).
- `ruff>=0.1` - Fast linter configured in `pyproject.toml` (`[tool.ruff]` targeting `py310`, line length 100, linting rules `E4`, `E7`, `E9`, `F`).

## Key Dependencies

**Runtime (Python):**
- None (`dependencies = []` in `pyproject.toml`).

**External System Binaries (Native Executables):**
- `ffmpeg` (required for video decoding): External executable on system `PATH`. Must support `-fps_mode passthrough`, `-f rawvideo`, `-pix_fmt rgb24`, and `-vf scale=W:H:flags=area`. Detected dynamically in `src/video.py` via `shutil.which("ffmpeg")`.
- `ffplay` (optional for audio playback): External executable on system `PATH`. Invoked in headless mode (`-vn -nodisp -autoexit -stats -loglevel warning`) in `src/audio.py` via `shutil.which("ffplay")`.
- `ffprobe` (optional for stream probing): External executable on system `PATH`. Probes container audio tracks (`-select_streams a`), video dimensions, FPS, and durations in `src/audio.py` and `src/sync.py`.

**Development & CI Dependencies:**
- `pytest>=7.0` - Test suite runner (`tests/`).
- `mypy>=1.0` - Type checking for `src/`.
- `ruff>=0.1` - Linting checks for code defects and syntax.

## Configuration

**Environment Variables (`RGB_ASCII_*`):**
- `RGB_ASCII_NO_ADAPTIVE` - `1` to disable dynamic load shedding (`--no-adaptive` CLI equivalent).
- `RGB_ASCII_HALF_BLOCK` - `1` to enable experimental half-block mode (`\u2580` characters with foreground top pixel and background bottom pixel).
- `RGB_ASCII_NO_COLOR` - `1` to force monochrome output (grayscale ASCII glyphs without ANSI color escapes).
- `RGB_ASCII_NO_AUDIO` - `1` to disable audio playback even when FFplay and audio streams exist.
- `RGB_ASCII_SMOOTHING` - Float in `[0.0, 1.0]` specifying temporal alpha blend factor (default: `0.0` disabled).
- `RGB_ASCII_FPS` - Integer override for target playback frame rate (overrides video stream FPS).
- `RGB_ASCII_PRESET` - Predefined ASCII luminance ramp (`default`, `dense`, `simple`, `blocks`).
- `RGB_ASCII_CHARS` - Custom ASCII character gradient string (lowest luminance first, highest luminance last).
- `RGB_ASCII_DEBUG` - `1` to print timing diagnostics, dropped frames, audio status, and A/V drift stats to `sys.stderr`.

**Build & Tool Configuration Files:**
- `pyproject.toml` - Declarative metadata, console entry points (`rgb-ascii = "src.main:main"`), package layout (`packages = ["src"]`), tool settings for pytest, mypy, and ruff.
- `requirements.txt` - Documentation of external native dependency expectations (standard library only).
- `.github/workflows/ci.yml` - Multi-OS GitHub Actions workflow matrix (Ubuntu, Windows) across Python 3.10 and 3.13.

## Platform Requirements

**Development:**
- Python >= 3.10 on Windows, macOS, or Linux.
- FFmpeg and FFplay binaries installed and on system PATH (for manual full-pipeline verification; automated test suite uses mocks and synthetic buffers).

**Production / Deployment:**
- CLI application runnable via `python -m src.main <video_path>` or console script `rgb-ascii <video_path>`.
- Any ANSI True Color (24-bit RGB) capable terminal emulator (Windows Terminal, iTerm2, Kitty, Alacritty, GNOME Terminal, xterm, etc.).

---

*Stack analysis: 2026-11-16*
