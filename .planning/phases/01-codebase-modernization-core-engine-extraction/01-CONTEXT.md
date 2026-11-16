# Phase 1: Codebase Modernization & Core Engine Extraction - Context

**Gathered:** 2026-11-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Audit, clean, and decouple the existing Python codebase, cleanly pruning terminal-only dependencies and interactive loops, and exposing a clean, robust media transformation core with 100% test, lint, and type health.

</domain>

<decisions>
## Implementation Decisions

### Legacy Code Archiving Strategy
- **D-01:** Clean Pruning to Git History. Delete terminal-only files (`src/terminal.py` and interactive TUI loop in `src/main.py`) rather than maintaining a dead `archive/` directory or `src/legacy/` subpackage. Git history retains past implementations if ever needed. — **Reversibility:** costly — Requires retrieving from git log and restoring deleted imports/tests to bring back.
- **D-02:** Strict No-Docker, Zero-Heavy-Infra Constraint. The user explicitly determined not to use Docker or complex container orchestration for daily development or deployment to eliminate maintenance overhead. All code must run natively in standard Python environments. — **Reversibility:** one-way — Architectural constraint shaping packaging, scripts, and deployment.

### Core Engine Structure & API Surface
- **D-03:** Flattened Layout with Clean `src/__init__.py` Facade. Keep core media modules in `src/` without creating extra subpackage nesting (`src/core/`). Export key classes (`RGBAsciiRenderer`, `FFmpegFrameReader`, `PlaybackTimeline`, `Config`) via `src/__init__.py` for simple, direct imports with zero import churn. — **Reversibility:** reversible — File moves to a subpackage later are straightforward if needed.

### Frame Rescaling & Dependency Boundary
- **D-04:** Dual-Path Architecture Matching Grainrad Paradigm. Following Grainrad (`grainrad.com`), real-time interactive preview scaling runs client-side on the GPU (WebGPU/WebGL2 in Phase 2). The Python backend relies on native FFmpeg scaling (`-vf scale`) for video transcoding, while retaining the pure-Python zero-dependency `resize_rgb24_area` for hermetic offline test execution and standalone byte-buffer processing without requiring external libraries like Pillow or NumPy. — **Reversibility:** reversible — Keeps dependencies at zero while retaining FFmpeg alignment.

### Test Suite Migration & Regression Safeguards
- **D-05:** Prune TUI Tests & Maintain 100% Core Engine Health. Remove tests that exclusively assert on terminal geometry, cursor control escapes, and TUI cleanup (`tests/test_terminal.py`, interactive parts of `tests/test_cleanup.py` and `tests/test_playback.py`). Keep all ~350+ core tests covering luminance mapping, Rec. 601 weighting, area averaging, video decoding, audio sync, and FFmpeg error classifications 100% passing. — **Reversibility:** costly — Would require re-creating terminal assertions if a CLI player were reintroduced.

### the agent's Discretion
- Module cleanup details in `src/renderer.py`, `src/video.py`, and `src/audio.py` (e.g., removing unused ANSI helper functions or dead terminal sizing calls).
- Exact helper signatures in `src/__init__.py` to provide a clean public export surface.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Specifications & Governance
- `.planning/PROJECT.md` — Core value, constraints, and architecture decisions
- `.planning/ROADMAP.md` — Phase 1 scope and success criteria (MODERN-01, MODERN-02, MODERN-03)
- `.planning/REQUIREMENTS.md` — Modernization requirements specification

### Core Engine Codebase
- `src/renderer.py` — Core luminance, ASCII mapping, and area-averaging algorithms
- `src/video.py` — FFmpeg subprocess decoding and error classification
- `src/audio.py` — Audio stream probing and player management
- `src/config.py` — Presets and runtime configuration dataclass
- `pyproject.toml` — Build configuration, pytest, mypy, and ruff settings

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/renderer.py`: `RGBAsciiRenderer`, `char_table_for`, `DEFAULT_CHARS`, `CHAR_PRESETS`, and `resize_rgb24_area`.
- `src/video.py`: `FFmpegFrameReader`, `classify_decode_termination`.
- `src/audio.py`: `AudioPlayer`, `detect_audio_status`.
- `src/sync.py`: `PlaybackTimeline`.
- `src/timing.py`: `FrameClock`.

### Established Patterns
- Zero third-party runtime dependencies (`dependencies = []`).
- Strict typing with Python 3.10+ pipe syntax (`from __future__ import annotations`).
- Subprocess safety with `shell=False` and explicit argument lists.

### Integration Points
- `src/__init__.py`: Will expose public facade for media extraction.
- `pyproject.toml`: Console script entry points and linter/typechecker targets.

</code_context>

<specifics>
## Specific Ideas

- **Grainrad Alignment:** Web client handles real-time visual processing (Grainrad style), Python backend handles heavy FFmpeg transcoding without heavy extra dependencies.
- **Maintenance Philosophy:** Strict no-Docker rule; maintain standard Python simplicity to keep day-to-day operations and deployments frictionless.

</specifics>

<deferred>
## Deferred Ideas

- Phase 2: Client-side WebGPU/WebGL2 shader engine and Stitch MCP studio UI.
- Phase 3: FastAPI endpoints and FFmpeg video transcoding export pipeline.

</deferred>

---

*Phase: 1-Codebase Modernization & Core Engine Extraction*
*Context gathered: 2026-11-16*
