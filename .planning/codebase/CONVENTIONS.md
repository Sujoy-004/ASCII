---
last_mapped_commit: a55586b3cdf529951d93b522083233d43fa80a2e
last_mapped_at: 2026-11-16
---
# Coding Conventions

**Analysis Date:** 2026-11-16

## Naming Patterns

**Files:**
- Lowercase snake_case across all Python modules (`src/adaptive.py`, `src/framesel.py`, `src/video.py`).
- Test files prefixed with `test_` matching functionality or subsystem (`tests/test_sync.py`, `tests/test_renderer.py`).

**Classes:**
- PascalCase for all classes, exceptions, and protocols (`FrameClock`, `AudioPlayer`, `FFmpegNotFoundError`, `TimestampSource`).
- Dataclasses use PascalCase (`Config`, `TimingStats`, `DropStats`, `PlaybackTimeline`).
- Enums use PascalCase with uppercase enum members (`AudioStatus.CONFIRMED`, `AudioStatus.ABSENT`).

**Functions & Methods:**
- snake_case for all public and private functions (`render_frame`, `sleep_until_deadline`, `char_table_for`).
- Internal/private helpers start with a single leading underscore (`_box_ranges`, `_find_ffmpeg`, `_decimal_str`).

**Variables & Constants:**
- Module-level constants in uppercase snake_case (`DEFAULT_CHARS`, `CHAR_PRESETS`, `FLUSH_GRACE`, `MAX_UTILIZATION`).
- Local variables in concise, descriptive snake_case (`frame_budget`, `ascii_frame`, `work_start`).

## Code Style

**Formatting & Linting:**
- Tool: Ruff (configured via `[tool.ruff]` in `pyproject.toml`).
- Line length: 100 characters max (`line-length = 100`).
- Target Python version: `py310` (`target-version = "py310"`).
- Selected lint rules: `E4`, `E7`, `E9`, `F` (strict syntax, undefined names, unused imports, pycodestyle errors without stylistic nitpicking).
- Type checking: Mypy (configured via `[tool.mypy]` in `pyproject.toml`).
  - Target: `files = ["src"]`, `python_version = "3.10"`.
  - Flags: `warn_unused_ignores = true`, `warn_redundant_casts = true`, `no_implicit_optional = true`.

## Import Organization

**Order:**
Strict 3-group order with future annotations at top:
1. `from __future__ import annotations` (present in all source files for modern typing support).
2. Standard library imports (e.g. `import os`, `import sys`, `import time`, `from dataclasses import dataclass`).
3. Internal project imports from `src.` package (e.g. `from src.config import Config`, `from src.renderer import RGBAsciiRenderer`).

**Rules:**
- All intra-project imports use absolute package imports prefixed with `src.` (`from src.config import Config`, not `from .config import Config`).
- No wildcard imports (`from ... import *` is never used).

## Error Handling

**Explicit, Typed Domain Exceptions:**
- Custom exceptions inherit from `RuntimeError` for operational/environment failures:
  - `FFmpegNotFoundError`, `FFmpegDecodeError` in `src/video.py`.
  - `FFplayNotFoundError`, `FFplayPlaybackError` in `src/audio.py`.
- Validation errors raise standard `ValueError` with clear messages:
  - `Config.__post_init__` verifies positive FPS, valid smoothing in `[0, 1]`, and non-empty char ramps.
  - Renderer checks for positive dimensions and matching byte slice lengths.

**Defensive Teardown & Resource Cleanup:**
- Main execution loops wrap operations in robust `try...finally` blocks to guarantee restoration of terminal cursor, reset of ANSI states, and graceful shutdown of background subprocesses.
- EOF and SIGINT (Ctrl+C) are caught cleanly, exiting with status 0 rather than dumping unhandled tracebacks to user consoles.

## Logging

**Framework:**
- No third-party logging frameworks. Diagnostic outputs write directly to `sys.stderr` when debug mode is enabled (`Config.debug` or `RGB_ASCII_DEBUG=1`).
- The standard output stream (`sys.stdout`) is reserved exclusively for raw ANSI frame presentation.

**Patterns:**
- Debug diagnostics are grouped into structured, aligned textual tables (`_report_stats`, `_report_frames`, `_report_audio`, `_report_sync` in `src/main.py`).

## Comments & Documentation

**Docstrings:**
- Triple-double-quoted module-level docstrings explaining architectural intent, constraints, and mathematical guarantees (e.g. `src/timing.py`, `src/sync.py`, `src/framesel.py`).
- Methods with non-obvious algorithms (e.g. area averaging in `src/renderer.py`, clock rebasing in `src/timing.py`) include detailed explanatory docstrings.

**Code Comments:**
- Inline comments focus on *why*, especially where subtle race conditions, pipe deadlocks, or FFmpeg quirks were resolved (e.g., explaining why stderr is buffered to a tempfile rather than an unread pipe).

## Function Design

**Type Hints:**
- Complete type annotations across all function arguments and return types.
- Type unions use modern pipe syntax `str | None`, `int | float` enabled by `from __future__ import annotations`.
- Protocols used where duck-typing provides better testability without cyclic imports (e.g. `TimestampSource` in `src/timing.py`).

**Purity & Performance:**
- Rendering and math calculations avoid allocations inside hot loops.
- `src/renderer.py` utilizes precalculated string lookup tables (`_decimal_str = tuple(str(i) for i in range(256))`) and memoized lookup tables (`_char_table_cache`) to avoid per-pixel formatting overhead.

## Module Design

**Single Responsibility & Encapsulation:**
- Each module owns a single distinct phase of the media/presentation lifecycle.
- Zero cyclic dependencies between modules.
- Standalone testability: modules like `RGBAsciiRenderer`, `FrameClock`, and `FrameSelector` can be instantiated and exercised with purely synthetic inputs without touching disk or starting subprocesses.

---

*Convention analysis: 2026-11-16*
