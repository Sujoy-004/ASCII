# Phase 1: Codebase Modernization & Core Engine Extraction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-16
**Phase:** 1-Codebase Modernization & Core Engine Extraction
**Areas discussed:** Legacy Code Archiving, Core Engine Structure & API Surface, Frame Rescaling & Dependency Boundary, Test Suite Migration & Regression Safeguards

---

## Legacy Code Archiving

| Option | Description | Selected |
|--------|-------------|----------|
| Top-Level `archive/` Directory | Physically move terminal.py and CLI loop to archive/ for complete separation from backend package | |
| Decoupled Subpackage `src/legacy/` | Keep under src/legacy/ so local terminal player remains runnable for smoke tests during development | |
| Clean Pruning to Git History | Delete terminal-only files completely, relying on Git history for legacy code | ✓ |

**User's choice:** Clean Pruning to Git History
**Notes:** User chose clean deletion of terminal-only code and explicitly specified avoiding Docker or complex infrastructure to eliminate daily maintenance friction.

---

## Core Engine Structure & API Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Flattened Layout with Clean `src/__init__.py` Facade | Keep it simple; zero import churn, core engine tools directly exported from src | ✓ |
| Structured Subpackage (`src/core/`) | Move core media modules into src/core/ for an explicit namespace boundary before web routes are added | |

**User's choice:** Flattened Layout with Clean `src/__init__.py` Facade
**Notes:** Prioritizes structural simplicity and avoids churn across module paths while cleanly exposing engine components.

---

## Frame Rescaling & Dependency Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Dual-Path: FFmpeg for Streams + Keep Pure-Python Resizer | Zero external dependencies, fast offline testing, FFmpeg handles video scaling | ✓ |
| FFmpeg-Exclusive Scaling | Drop pure-Python resizer; rely 100% on FFmpeg for all scaling tasks | |
| Add Pillow / NumPy Bridge | Introduce Pillow for fast C-accelerated image manipulation in Python | |

**User's choice:** Dual-Path matching Grainrad.com paradigm
**Notes:** User directed alignment with grainrad.com. In-browser GPU shaders handle real-time client scaling, while Python backend uses native FFmpeg scaling for transcoding and preserves pure-Python box-resizing for offline hermetic testing.

---

## Test Suite Migration & Regression Safeguards

| Option | Description | Selected |
|--------|-------------|----------|
| Prune TUI Tests, Maintain 100% Core Engine Health | Remove terminal-only tests; keep all ~350+ core media, math, and FFmpeg tests 100% passing | ✓ |
| Convert TUI Tests to Headless Mock Sinks | Keep all 387 tests by adapting terminal assertions to mock in-memory sinks | |

**User's choice:** Prune TUI Tests, Maintain 100% Core Engine Health
**Notes:** Remove the ~30 terminal-only tests; maintain 100% passing status across the ~350+ core media, luminance, and FFmpeg tests.

---

## The Agent's Discretion

- Fine-tuning module cleanups in `src/renderer.py`, `src/video.py`, and `src/audio.py` (stripping unused terminal helpers).
- Selecting export symbols in `src/__init__.py`.

## Deferred Ideas

- Phase 2: Client-side WebGPU/WebGL2 shader engine and Stitch MCP studio UI.
- Phase 3: FastAPI endpoints and FFmpeg video transcoding export pipeline.
