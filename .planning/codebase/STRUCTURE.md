---
last_mapped_commit: e321c7dc0149e147f0982b5600f9b94d3f186120
last_mapped_at: 2026-11-16
---
# Codebase Structure

**Analysis Date:** 2026-11-16

## Directory Layout

```
ASCII/
├── .github/
│   └── workflows/
│       └── ci.yml               # Multi-OS CI testing matrix (Python 3.10/3.13 on Ubuntu/Windows)
├── .planning/                   # GSD project and planning state (local or tracked)
│   └── codebase/                # Codebase intelligence documents
├── assets/                      # Sample multimedia assets and historical test fixtures
├── src/                         # Core Python package (flat layout inside src/)
│   ├── __init__.py              # Public API facade re-exporting core symbols
│   ├── adaptive.py              # Dynamic quality controller and load shedding
│   ├── audio.py                 # FFplay audio subprocess management and stream detection
│   ├── config.py                # Runtime configuration and character presets
│   ├── framesel.py              # Frame selection and real-time lag recovery / drop policy
│   ├── main.py                  # CLI entry point, argument parsing, main playback loop
│   ├── renderer.py              # RGB24 to ASCII & ANSI True Color rendering engine
│   ├── smoothing.py             # Optional temporal RGB24 smoothing
│   ├── sync.py                  # Playback timeline, A/V synchronization, duration probing
│   ├── timing.py                # Frame clock, monotonic deadlines, pacing calculations
│   └── video.py                 # FFmpeg video decoding subprocess and frame reader
├── tests/                       # Hermetic test suite (380+ unit and integration tests)
│   ├── test_adaptive.py         # Tests for QualityController and lever adjustments
│   ├── test_audio.py            # Tests for AudioPlayer and FFplay process handling
│   ├── test_bench.py            # Tests for benchmark harness smoke tests
│   ├── test_brightness.py       # Tests for luminance calculation and character mapping
│   ├── test_cleanup.py          # Tests for process shutdown, signal handling, terminal cleanup
│   ├── test_cli.py              # Tests for CLI flags and environment variable parsing
│   ├── test_frame_reader.py     # Tests for FFmpegFrameReader and stderr classification
│   ├── test_framesel.py         # Tests for FrameSelector and drop logic
│   ├── test_media_errors.py     # Tests for handling corrupt media, missing files, bad inputs
│   ├── test_playback.py         # Tests for end-to-end playback loops with mock readers
│   ├── test_renderer.py         # Tests for RGBAsciiRenderer, ANSI formatting, block modes
│   ├── test_sampling.py         # Tests for nearest-neighbor and area-averaging re-scaling
│   ├── test_smoothing.py        # Tests for TemporalSmoother RGB24 alpha blending
│   ├── test_startup_sync.py     # Tests for startup latency absorption and clock adoption
│   ├── test_sync.py             # Tests for PlaybackTimeline, completion timeouts, A/V drift
│   ├── test_terminal.py         # Tests for TerminalRenderer size and aspect ratio math
│   ├── test_timestamp_stream.py # Tests for variable frame rate timestamp streams
│   ├── test_timing.py           # Tests for FrameClock absolute deadlines and drift prevention
│   └── test_vfr_tail.py         # Tests for variable-frame-rate trailing frame pacing
├── .gitignore                   # Git exclusion rules
├── AGENTS.md                    # Developer and AI agent guidelines (simplicity, surgical changes)
├── bench.py                     # Deterministic rendering benchmark harness
├── pyproject.toml               # Package build metadata, tool configurations (pytest, mypy, ruff)
├── README.md                    # User and developer documentation
└── requirements.txt             # Information on standard library design and native dependencies
```

## Directory Purposes

**`src/`:**
- Purpose: Contains all production code for the `rgb-ascii-renderer` package.
- Contains: Single-responsibility modules managing configuration, subprocesses, synchronization, frame conditioning, rendering, and output presentation.
- Key files:
  - `src/main.py`: Top-level CLI and playback orchestrator.
  - `src/renderer.py`: Core True Color ASCII conversion and box-resizing routines.
  - `src/timing.py`: Authoritative pacing engine and deadline scheduler.
  - `src/sync.py`: Playback timeline data structures and A/V sync management.

**`tests/`:**
- Purpose: Automated test suite verifying every component in isolation and end-to-end.
- Contains: Deterministic, hermetic tests relying on mocks and synthetic byte streams.
- Key files:
  - `tests/test_playback.py`: Full playback loop tests.
  - `tests/test_sync.py`: Synchronization and drift tests.
  - `tests/test_renderer.py`: Color and glyph fidelity tests.

**`.github/workflows/`:**
- Purpose: Automated CI workflows.
- Contains: `ci.yml` defining multi-platform automated testing, compilation, typing, linting, and smoke benchmarks.

## Key File Locations

**Entry Points:**
- `src/main.py`: Console entry point `rgb-ascii` and `python -m src.main`.
- `bench.py`: Standalone benchmark runner `python bench.py`.

**Configuration:**
- `pyproject.toml`: Package build configuration, packaging layout, tool settings (mypy, ruff, pytest).
- `src/config.py`: Application runtime settings dataclass and predefined ASCII gradients.

**Subprocess / Hardware Interfaces:**
- `src/video.py`: FFmpeg subprocess interaction.
- `src/audio.py`: FFplay subprocess interaction.

## Naming Conventions

**Files:**
- Source files: Lowercase snake_case (e.g. `src/framesel.py`, `src/timing.py`).
- Test files: Prefixed with `test_` matching corresponding module or capability (e.g. `tests/test_framesel.py`, `tests/test_timing.py`).
- Documentation files: Uppercase `.md` (e.g. `README.md`, `AGENTS.md`).

**Classes & Functions:**
- Classes: PascalCase (e.g. `FrameClock`, `RGBAsciiRenderer`, `PlaybackTimeline`).
- Functions & Methods: Lowercase snake_case (e.g. `render_frame`, `sleep_until_deadline`, `detect_audio_status`).
- Constants / Globals: Uppercase snake_case (e.g. `DEFAULT_CHARS`, `CHAR_PRESETS`, `FLUSH_GRACE`).
- Private helpers: Leading underscore (e.g. `_box_ranges`, `_find_ffmpeg`, `_decimal_str`).

## Where to Add New Code

**New Output Format or Color Mode:**
- Implementation: Add rendering routines to `src/renderer.py` (e.g., alongside `render_frame_blocks`).
- Configuration: Add flags to `Config` in `src/config.py` and CLI options in `src/main.py`.
- Tests: Add corresponding tests in `tests/test_renderer.py` and `tests/test_cli.py`.

**New Playback Control or Filter:**
- Implementation: Add filter/stage in `src/` following the pattern of `src/smoothing.py` or `src/framesel.py`.
- Integration: Hook into the processing pipeline in `src/main.py:run`.
- Tests: Add a dedicated `tests/test_<feature>.py`.

**Performance Benchmarks:**
- Implementation: Add sizing scenarios or render methods to `bench.py`.
- Verification: Validate via `tests/test_bench.py`.

## Special Directories

**`.planning/`:**
- Purpose: Project roadmap, milestone specifications, and codebase state documents for GSD workflows.
- Generated: Semi-automated by GSD commands.
- Committed: Yes (configured via `commit_docs: true` in GSD config).

**`__pycache__/`:**
- Purpose: Compiled Python bytecode caches (`*.pyc`).
- Generated: Yes (automatically by CPython).
- Committed: No (ignored via `.gitignore`).

---

*Structure analysis: 2026-11-16*
