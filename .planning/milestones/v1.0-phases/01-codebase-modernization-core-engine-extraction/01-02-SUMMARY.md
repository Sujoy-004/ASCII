---
phase: 01-codebase-modernization-core-engine-extraction
plan: "02"
subsystem: core-engine
tags: [python, pytest, mypy, ruff, test-suite, headless, terminal-pruning, verification]

# Dependency graph
requires:
  - phase: 01-01
    provides: headless core engine (src/__init__.py 36-symbol facade, decoupled run() with duck-typed sink, src/terminal.py deleted, status_rows purged) and its known 9-item broken test start state (test_terminal.py collection error + 8 TerminalRenderer monkeypatch failures)
provides:
  - "Test suite pruned of terminal-only coverage: tests/test_terminal.py deleted to git history per D-05"
  - "Decoupled-sink test doubles: 4 src.main.TerminalRenderer monkeypatches replaced with _headless_output_size (2,2) pins; the real _StdoutSink runs end-to-end under capsys"
  - "100% hermetic suite pass: 387/387 tests green with zero terminal dependencies per MODERN-03"
  - "Zero-error static typing: mypy 'Success: no issues found in 11 source files' per MODERN-02"
  - "Zero-error lint: ruff 'All checks passed!' across src/ and tests/ per MODERN-02"
  - "pyproject.toml verified accurate for the headless core engine (setuptools targets src only, zero runtime deps, Python >=3.10)"
affects: [02 (client shader pipeline consumes the certified core), 03 (FastAPI backend consumes the facade), phase verification]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 1816        # chars/4 over the realized diff (7,266 bytes, 3 files, +20/-90), plan estimated 45,000
  tasks: 2
  commits: 1          # MEASURED: git rev-list --count 2ac411c..HEAD at SUMMARY write

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Headless size injection: tests pin src.main._headless_output_size (the function that replaced TerminalRenderer.output_size) to the grid their frame fakes are sized for"
    - "Real-sink integration testing: main()-level tests run the actual _StdoutSink under capsys instead of mocking the sink"

key-files:
  created: []
  modified:
    - tests/test_media_errors.py
    - tests/test_timestamp_stream.py
  deleted:
    - tests/test_terminal.py

key-decisions:
  - "Adapted (not removed) the 4 TerminalRenderer monkeypatches: pinned src.main._headless_output_size to (2,2) — the sizing function that inherited the terminal's output_size role — so main()-level tests still exercise the real render loop over real 2x2 frames through the real _StdoutSink under capsys"
  - "FakeTerminal fakes kept as duck-typed run() sinks unchanged: 01-01's sink protocol (write_frame/output_size/refresh_size/clear/restore via getattr) already made them valid frame consumers; no cursor-escape or ANSI-clear assertions existed to prune in test_cleanup.py/test_playback.py, so those files were audited and left untouched"
  - "Task 2 is verification-only and produced no commit: pytest (387 passed), mypy (Success), ruff (All checks passed!) all green with pyproject.toml audited accurate, so there was nothing to commit"

patterns-established:
  - "Size-pin mock pattern: _headless_output_size is the single injection point for CLI grid sizing in tests"
  - "Zero-error gates: python -m pytest -q, python -m mypy src, python -m ruff check . are the phase's green baseline for future changes"

requirements-completed: [MODERN-02, MODERN-03]

coverage:
  - id: D1
    description: "Terminal-only test file pruned to git history: tests/test_terminal.py deleted per D-05 (8 terminal geometry/aspect/status_rows tests removed with src/terminal.py)"
    requirement: MODERN-03
    verification:
      - kind: other
        ref: "Test-Path tests/test_terminal.py -> False (verified on disk after commit 9f4a5c8)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Decoupled-sink test doubles: zero tests import or monkeypatch src.terminal or src.main.TerminalRenderer; 54 integration tests in test_cleanup/test_playback/test_media_errors/test_timestamp_stream pass"
    requirement: MODERN-03
    verification:
      - kind: unit
        ref: "python -m pytest tests/test_cleanup.py tests/test_playback.py tests/test_media_errors.py tests/test_timestamp_stream.py -q (54 passed)"
        status: pass
      - kind: other
        ref: "grep src.terminal|TerminalRenderer over tests/ -> only test_facade.py negative assertions (D-01 contract) remain"
        status: pass
    human_judgment: false
  - id: D3
    description: "Hermetic full-suite pass: all 387 tests (379 core + 8 facade) green with 100% success rate, no terminal dependencies, offline fakes only (T-01-05)"
    requirement: MODERN-03
    verification:
      - kind: integration
        ref: "python -m pytest -q (387 passed in 7.96s)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Zero-error static typing across src/ including the facade per MODERN-02 (Python 3.10 target)"
    requirement: MODERN-02
    verification:
      - kind: other
        ref: "python -m mypy src (Success: no issues found in 11 source files)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Zero-error lint across src/ and tests/ per MODERN-02 (ruff E4/E7/E9/F gate)"
    requirement: MODERN-02
    verification:
      - kind: other
        ref: "python -m ruff check . (All checks passed!)"
        status: pass
    human_judgment: false
  - id: D6
    description: "pyproject.toml metadata verified against the headless core engine: setuptools flat discovery targets src only (T-01-04), zero runtime dependencies (T-01-SC), requires-python >=3.10, console entrypoint rgb-ascii = src.main:main intact"
    requirement: MODERN-02
    verification:
      - kind: other
        ref: "pyproject.toml audit: packages=['src'], dependencies=[], requires-python>=3.10, [tool.mypy] files=['src']/py3.10, [tool.ruff] target py310 — all confirmed by read"
        status: pass
    human_judgment: false

# Metrics
duration: 9min
completed: 2026-11-16
status: complete
---

# Phase 01 Plan 02: Test Suite Modernization & Full Verification Summary

**Terminal-only tests pruned to git history, 4 stale TerminalRenderer monkeypatches replaced with headless `_headless_output_size` pins, and the whole engine certified green: 387/387 tests hermetically, mypy zero errors in 11 source files, ruff all-checks-passed.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-11-16T09:13:40Z
- **Completed:** 2026-11-16T09:22:58Z
- **Tasks:** 2
- **Files modified:** 3 (1 deleted, 2 modified)

## Accomplishments

- Deleted `tests/test_terminal.py` per D-05 — the 8 terminal-geometry/aspect-ratio/status_rows tests are pruned to git history alongside `src/terminal.py` (deleted in 01-01)
- Adapted all 4 `monkeypatch.setattr("src.main.TerminalRenderer", FakeTerminal)` call sites (test_media_errors.py ×1, test_timestamp_stream.py ×3) to pin `src.main._headless_output_size` to (2, 2), the sizing function that inherited the terminal's `output_size` role — main()-level tests now drive the real render loop through the real `_StdoutSink` under capsys
- Fixed the entire wave-1 known-failure list (1 collection error + 8 failures) as declared planned work; the suite is 100% green
- Certified the core engine: `python -m pytest -q` → 387 passed; `python -m mypy src` → "Success: no issues found in 11 source files"; `python -m ruff check .` → "All checks passed!"
- Audited `pyproject.toml` against the headless core engine: keywords/classifiers/tool configs all accurate, zero edits required

## Task Commits

Each task was committed atomically:

1. **Task 1: Prune terminal-only tests and update test suite mocks for decoupled frame sink** - `9f4a5c8` (refactor)
2. **Task 2: Full regression verification, hermetic test suite, static typing, and lint checks** - verification-only, no commit (all three gates already green; no file changes to commit)

## Files Created/Modified

- `tests/test_terminal.py` - DELETED per D-05 (terminal geometry, viewport aspect, refresh_size, status_rows tests)
- `tests/test_media_errors.py` - TerminalRenderer monkeypatch → `_headless_output_size` (2,2) pin; FakeTerminal kept as duck-typed run() sink
- `tests/test_timestamp_stream.py` - 3 TerminalRenderer monkeypatches → same `_headless_output_size` pin; FakeTerminal kept for direct run() wiring tests
- `tests/test_cleanup.py`, `tests/test_playback.py` - audited, no edits needed (already duck-typed sinks; no ANSI/cursor assertions existed)
- `pyproject.toml` - audited, no edits needed (accurate for headless core engine)

## Decisions Made

- **Adapt, don't remove, the sink injection:** deleting the `TerminalRenderer` monkeypatches outright would have opened the reader at the default 80-column headless grid while the fakes stream 2×2-sized frames — the tests would still pass but vacuously (immediate EOF, zero frames rendered). Pinning `_headless_output_size` to (2, 2) preserves the original tests' intent: a real decode→render→write cycle over the fake frame stream.
- **Real `_StdoutSink` under capsys:** the main()-level tests no longer mock the sink at all — the actual headless sink writes captured stdout, so exit-code and stderr-label assertions now run end-to-end through the decoupled pipeline.
- **No metadata churn in pyproject.toml:** verification confirmed `packages = ["src"]` (T-01-04), `dependencies = []` (T-01-SC), `requires-python = ">=3.10"`, mypy/ruff targets — the ANSI-truecolor output format keeps the terminal-domain keyword/classifier accurate for the headless engine.

## Deviations from Plan

None - plan executed exactly as written. (The wave-1 test failures and collection error listed in 01-01-SUMMARY §Issues Encountered were this plan's declared start state and were fixed as planned Task 1 work, not deviations.)

**Total deviations:** 0 auto-fixed
**Impact on plan:** none

## Issues Encountered

- None. The declared 9-item broken start state (1 collection error, 8 monkeypatch failures) cleared with exactly the planned edits; no unexpected failures surfaced in the full 387-test run, mypy sweep, or ruff sweep.
- `git rm` on Windows emitted a benign LF→CRLF working-copy warning for test_timestamp_stream.py; content committed as intended.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Phase 01 is complete (2 of 2 plans):** the core engine is certified — 36-symbol facade, duck-typed sink, 387/387 hermetic tests, zero mypy/ruff errors, zero runtime dependencies — ready for phase verification (`/gsd-verify-work 01`)
- Phase 2 (client shader pipeline) and Phase 3 (FastAPI backend) can consume the facade (`from src import ...`) against this now-stable, fully-green baseline
- Green gates to protect going forward: `python -m pytest -q`, `python -m mypy src`, `python -m ruff check .`

---
*Phase: 01-codebase-modernization-core-engine-extraction*
*Completed: 2026-11-16*

## Self-Check: PASSED

- Key files verified on disk: `tests/test_media_errors.py`, `tests/test_timestamp_stream.py`, `tests/test_cleanup.py`, `tests/test_playback.py` FOUND; `tests/test_terminal.py` confirmed ABSENT (Test-Path → False)
- Commit verified in HEAD history: `9f4a5c8` (Task 1) — `git merge-base --is-ancestor` → 0
- `gsd_run check evaluation-scope --plan "01-02" --commits-only`: 1 commit (`9f4a5c8`), status `resolved`, nothing missing on disk
- Plan-level verification re-run and green: `python -m pytest -q` → 387 passed; `python -m mypy src` → Success (11 files); `python -m ruff check .` → All checks passed!
- Acceptance criteria re-run: test_terminal.py absent ✓; zero tests import/monkeypatch src.terminal or src.main.TerminalRenderer (only test_facade.py negative assertions remain) ✓; all 4 integration files pass (54 tests) ✓; mypy "Success: no issues found" ✓; ruff "All checks passed!" ✓
