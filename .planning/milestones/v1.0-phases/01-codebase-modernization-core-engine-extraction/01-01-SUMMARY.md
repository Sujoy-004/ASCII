---
phase: 01-codebase-modernization-core-engine-extraction
plan: "01"
subsystem: core-engine
tags: [python, ffmpeg, ascii, facade, headless, terminal-pruning, refactoring]

# Dependency graph
requires:
  - phase: none
    provides: existing Python stdlib-only media engine (renderer, video, audio, sync, timing, framesel, smoothing, adaptive modules)
provides:
  - "src/__init__.py public facade exporting 36 core engine symbols with explicit __all__ (D-03)"
  - "src/terminal.py deleted — terminal-only module pruned to git history (D-01)"
  - "src/main.py decoupled from TerminalRenderer: duck-typed sink in run(), headless _StdoutSink CLI, aspect-derived _headless_output_size"
  - "src/config.py purged of terminal-only status_rows (D-01)"
  - "tests/test_facade.py tracer proving end-to-end rendering through the facade without terminal dependencies"
affects: [01-02 (test-suite modernization), 03 (FastAPI backend consumes the facade), 02 (client shader pipeline)]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 5275        # chars/4 over the realized diff (21,098 chars), plan estimated 45,000
  tasks: 2
  commits: 2          # MEASURED: git rev-list --count 44d0f71..HEAD

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Duck-typed frame sink protocol in run(): write_frame/callable/None output, optional refresh_size/output_size/clear/restore discovered via getattr"
    - "Package facade pattern: src/__init__.py re-exports core symbols, zero import churn for downstream consumers"

key-files:
  created:
    - tests/test_facade.py
  modified:
    - src/__init__.py
    - src/main.py
    - src/config.py
  deleted:
    - src/terminal.py

key-decisions:
  - "run() decoupled to a duck-typed sink (third positional parameter, no default — `= None` in that position is a SyntaxError before non-default clock); all 8 existing run() call sites keep working unchanged (379 tests pass)"
  - "src/__init__.py exports 36 symbols — the plan's own action enumerates 36 names; its prose said '30', resolved in favor of the authoritative enumeration"
  - "Headless CLI grid derived from probed video aspect at 80 columns (DEFAULT_VIDEO_ASPECT moved from terminal.py into main.py); _StdoutSink stays minimal (write_frame only) and relies on run()'s duck-typing for optional protocol members"
  - "git.allow_default_branch_commits=true set in .planning/config.json as the sanctioned #3819 override for this sequential main-tree dispatch (branching_strategy=none)"

patterns-established:
  - "Facade-first imports: `from src import RGBAsciiRenderer` is the supported public surface for Phase 3 FastAPI and tests"
  - "Sink protocol: any object with write_frame(str) (or callable) is a valid frame consumer of src.main.run"

requirements-completed: [MODERN-01]

coverage:
  - id: D1
    description: "Terminal-only module pruned: src/terminal.py deleted from disk, retained in git history (D-01)"
    requirement: MODERN-01
    verification:
      - kind: unit
        ref: "tests/test_facade.py#test_terminal_module_is_pruned_from_disk"
        status: pass
    human_judgment: false
  - id: D2
    description: "Public facade: src/__init__.py re-exports 36 core engine symbols with explicit __all__, importable cleanly (D-03)"
    requirement: MODERN-01
    verification:
      - kind: unit
        ref: "tests/test_facade.py#test_facade_exports_every_declared_symbol"
        status: pass
      - kind: unit
        ref: "tests/test_facade.py#test_core_symbols_import_directly_from_src"
        status: pass
    human_judgment: false
  - id: D3
    description: "main.py decoupled from TerminalRenderer: run(sink) duck-typed frame sink, zero src.terminal imports/references (D-01)"
    requirement: MODERN-01
    verification:
      - kind: unit
        ref: "tests/test_facade.py#test_main_is_decoupled_from_terminal_renderer"
        status: pass
      - kind: integration
        ref: "tests/test_cleanup.py + tests/test_playback.py + tests/test_sync.py (379 run()-level tests pass unchanged with FakeTerminal sinks)"
        status: pass
    human_judgment: false
  - id: D4
    description: "status_rows purged from Config while all media settings and validations remain (D-01)"
    requirement: MODERN-01
    verification:
      - kind: other
        ref: "python -c \"from src.config import Config; assert not hasattr(Config(), 'status_rows')\""
        status: pass
      - kind: unit
        ref: "tests/test_cli.py (27 tests on config_from_args parity)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Tracer: synthetic 4x4 RGB24 frame through resize_rgb24_area + render_frame produces ASCII via the facade, with no terminal import in the chain"
    requirement: MODERN-01
    verification:
      - kind: unit
        ref: "tests/test_facade.py#test_end_to_end_frame_pipeline"
        status: pass
      - kind: unit
        ref: "tests/test_facade.py#test_facade_import_does_not_load_terminal_module"
        status: pass
    human_judgment: false
  - id: D6
    description: "Headless CLI actually plays a real media file to plain-text stdout without terminal escape sequences"
    requirement: MODERN-01
    verification: []
    human_judgment: true
    rationale: "End-to-end CLI output against a real FFmpeg-decoded media file requires FFmpeg binaries and human inspection of stdout formatting; automated coverage covers parsing (test_cli) and the sink contract (integration fakes), not real-media rendering."

# Metrics
duration: 22min
completed: 2026-11-16
status: complete
---

# Phase 01 Plan 01: Core Engine Pruning & Facade Summary

**Terminal module pruned to git history, 36-symbol public facade exported from `src`, main.py decoupled to a duck-typed headless frame sink, and `status_rows` purged — 379 existing run()-level tests pass unchanged.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-11-16T08:17:46Z
- **Completed:** 2026-11-16T08:40:02Z
- **Tasks:** 2
- **Files modified:** 5 (1 deleted, 3 modified, 1 created)

## Accomplishments

- Deleted `src/terminal.py` per D-01 — clean pruning to git history, no archive/ or legacy/ folder
- Populated `src/__init__.py` facade per D-03: docstring, `from __future__ import annotations`, re-exports of all core classes/functions/exceptions across 9 modules, explicit `__all__` with 36 symbols
- Decoupled `src/main.py`: `run()` now takes a duck-typed `sink: Any` (write_frame/callable/None output; optional refresh_size/output_size/clear discovered via getattr; restore invoked when present); `main()` uses a minimal `_StdoutSink` writing plain-text frames to stdout and `_headless_output_size` deriving an 80-column aspect-preserving grid
- Purged `status_rows: int = 2` and its viewport-reservation comment from `Config`; all other fields and `__post_init__` validations intact
- Created `tests/test_facade.py` tracer (8 tests): facade `__all__` completeness, direct core-symbol imports, Rec. 601 luminance spot-checks, 4x4→2x2 area-rescale + ASCII render pipeline, terminal-pruning assertions, and no-terminal-import-in-chain guarantee

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end core engine import and frame render tracer (prune terminal.py, decouple main.py, export facade)** - `2a19dea` (feat)
2. **Task 2: Purge terminal-only status_rows from Config and align CLI parser** - `5962752` (refactor)

## Files Created/Modified

- `src/terminal.py` - DELETED per D-01 (terminal control, TerminalRenderer, DEFAULT_VIDEO_ASPECT host)
- `src/__init__.py` - Public package facade: 36 core engine symbols, explicit `__all__`
- `src/main.py` - TerminalRenderer import removed; `run(sink)` duck-typed frame sink; `_StdoutSink` + `_headless_output_size` headless CLI path; `DEFAULT_VIDEO_ASPECT` relocated here; help text and comments updated to headless semantics
- `src/config.py` - `status_rows` field and comment removed
- `tests/test_facade.py` - NEW tracer: 8 tests over the facade and pruning contract

## Decisions Made

- **`sink` has no default value:** the plan's `sink: Any = None` is a SyntaxError at the third positional slot (non-default `clock` follows). Shipped `sink: Any` without a default — all 8 existing `run()` call sites pass the sink positionally and remain source-compatible; `None` is still passable explicitly. Verified by 379 passing run()-level tests.
- **36 symbols, not 30:** the plan prose said "__all__ containing 30 core symbols" while its own action enumerated 36 names (identical to research Pattern 1's `__all__` and the plan's artifacts list). Resolved in favor of the enumerated list.
- **Minimal headless sink:** `_StdoutSink` defines only `write_frame`; run()'s duck-typing treats absent `refresh_size`/`output_size`/`clear`/`restore` as no-ops, so protocol surface is opt-in.
- **Aspect-preserving headless grid:** `_headless_output_size` reuses the retired terminal sizing math (`rows = cols * char_aspect / video_aspect`, 16:9 default) at a fixed 80 columns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tracer glyph-set assertion included the newline row separator**
- **Found during:** Task 1 (test_end_to_end_frame_pipeline)
- **Issue:** `set(ascii_frame) <= set(DEFAULT_CHARS)` failed because the rendered frame contains `\n` separators between rows
- **Fix:** Excluded the separator: `set(ascii_frame) - {"\n"} <= set(DEFAULT_CHARS)`
- **Files modified:** tests/test_facade.py
- **Verification:** 8/8 tests pass (`python -m pytest tests/test_facade.py -x`)
- **Committed in:** 2a19dea (Task 1 commit)

**2. [Plan-text discrepancy - resolved] `__all__` size: 30 (prose) vs 36 (enumeration)**
- **Found during:** Task 1 (facade authoring)
- **Issue:** Plan acceptance criterion says "__all__ containing 30 core symbols" but the action enumerates 36 import names, matching 01-RESEARCH.md Pattern 1 and the plan's own "Artifacts this phase produces" list
- **Fix:** Exported all 36 enumerated symbols; treated the enumeration as authoritative
- **Files modified:** src/__init__.py
- **Verification:** `python -c "import src; assert len(src.__all__) == 36"` and full export check pass
- **Committed in:** 2a19dea (Task 1 commit)

**3. [Rule 1 - Bug] `sink: Any = None` literal signature impossible**
- **Found during:** Task 1 (run() signature change)
- **Issue:** A defaulted parameter before non-default `clock: FrameClock` is a Python SyntaxError
- **Fix:** Kept position 3 without a default (`sink: Any`); documented in run()'s docstring that None discards output
- **Files modified:** src/main.py
- **Verification:** All 379 run()-level tests pass unchanged
- **Committed in:** 2a19dea (Task 1 commit)

---

**Total deviations:** 3 auto-handled (2 bug fixes, 1 plan-text discrepancy resolved in favor of the enumeration)
**Impact on plan:** All fixes necessary for correctness or fidelity to the plan's enumerated contract. No scope creep.

## Issues Encountered

- **Known inter-plan breakage (owned by plan 01-02, not this plan):** the full suite currently has 8 failures (`test_media_errors.py` ×5, `test_timestamp_stream.py` ×3 — tests that `monkeypatch.setattr("src.main.TerminalRenderer", ...)`, an attribute that no longer exists) plus a collection error in `tests/test_terminal.py` (`ModuleNotFoundError: No module named 'src.terminal'`). Both are exactly 01-02 Task 1's declared scope: delete `tests/test_terminal.py` and remove/adapt the `src.main.TerminalRenderer` monkeypatches. This plan's verify scope (`test_facade` + `test_cli`) is 35/35 green.
- Stale `.mypy_cache`/`__pycache__` bytecode for the deleted terminal module is regenerated by tooling; 01-02's `mypy`/`ruff` full sweep will confirm clean state.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Core engine is headless and zero-dependency: the facade (`from src import ...`) is the stable consumption surface for Phase 3 FastAPI endpoints
- 379 run()-level tests prove the duck-typed sink preserves every existing integration contract (FakeTerminal fakes work unmodified)
- 01-02 starting state: 8 known failures + 1 collection error, all matching its Task 1 action items precisely; after its fixes the suite should reach 100% with `mypy src` and `ruff check .` zero-error gates
- `pyproject.toml` console entrypoint `rgb-ascii = src.main:main` remains functional as a headless CLI

---
*Phase: 01-codebase-modernization-core-engine-extraction*
*Completed: 2026-11-16*

## Self-Check: PASSED

- Key files verified on disk: `src/__init__.py`, `src/main.py`, `src/config.py`, `tests/test_facade.py` FOUND; `src/terminal.py` confirmed absent
- Commits verified in HEAD history: `2a19dea` (Task 1), `5962752` (Task 2)
- `gsd_run check evaluation-scope --plan "01-01" --commits-only`: 2 commits, status `resolved`, none missing on disk
- Acceptance criteria re-run: all 4 Task 1 criteria + all 3 Task 2 criteria PASS (`__all__` complete with 36 exports, terminal.py absent, main.py clean, `status_rows` gone, `Config()` instantiates)
- Plan-level verification re-run: `python -m pytest tests/test_facade.py tests/test_cli.py -x` → 35 passed; `import src` exposes 36 symbols
