---
phase: 01-codebase-modernization-core-engine-extraction
plan: "03"
subsystem: cli-sink
tags: [python, pytest, mypy, ruff, tty, stdout-sink, gap-closure, live-resize]

# Dependency graph
requires:
  - phase: 01-01
    provides: headless core engine, duck-typed sink protocol in run()
  - phase: 01-02
    provides: clean 387-test baseline, zero-error mypy/ruff gates
provides:
  - "Dual-mode stdout sink: in-place terminal redraw via clear + cursor-home when stdout is a TTY, byte-identical plain text with trailing newline when piped"
  - "Aspect-fit TTY grid sizing: _tty_output_size fits grid to terminal using shutil.get_terminal_size and config.char_aspect"
  - "Live terminal-resize support: refresh_size(), output_size(), and clear() in _StdoutSink handle dynamic terminal window resizing mid-playback"
  - "Hermetic TTY test suite: 21 comprehensive unit and integration tests in tests/test_tty_sink.py covering all seams, aspects, and protocol states"
  - "Zero regression across all 408 tests, mypy, and ruff checks"
  - "Triaged code review disposition record with finding IN-03 resolved and 7 deferred items recorded"
affects: [Phase 01 verification, Phase 02 UI/UX redesign]

# Actuals
actuals:
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Dual-mode frame sink: gates ANSI cursor escapes strictly on _stdout_is_tty()"
    - "Aspect-fit grid math: (cols * cf) / rows == video_aspect bounded by terminal dimensions"
    - "Duck-typed sink protocol: getattr-based probing of optional resize members"

key-files:
  created:
    - tests/test_tty_sink.py
  modified:
    - src/main.py
    - .planning/phases/01-codebase-modernization-core-engine-extraction/01-REVIEW-DISPOSITION.md

key-decisions:
  - "Implemented Option A from UAT: TTY-fit sizing with isatty-guarded cursor-home animation without restoring src/terminal.py or introducing any new dependencies (stdlib shutil only)"
  - "Preserved non-TTY piped output byte-identity: piped stdout receives exact frame strings plus newlines without ANSI escape sequences"
  - "Triaged open code-review findings in 01-REVIEW-DISPOSITION.md: IN-03 resolved, WR-01 through WR-04 and IN-01, IN-02, IN-04 deferred to Phase 2/3"

patterns-established:
  - "Single isatty source of truth: _stdout_is_tty() ensures sizing and animation mode never disagree"
  - "Clean idempotence on teardown: restore() runs safely across multiple finally paths without duplicate emissions"

requirements-completed: [MODERN-01, MODERN-02, MODERN-03]

coverage:
  - id: GAP-01
    description: "Real-TTY playback watchability restored via aspect-fit grid sizing and in-place cursor-home animation"
    requirement: MODERN-01
    verification:
      - kind: automated
        ref: "python -m pytest tests/test_tty_sink.py -q (21 passed)"
        status: pass
  - id: GATE-01
    description: "Full test suite hermetic pass with zero regressions"
    requirement: MODERN-03
    verification:
      - kind: automated
        ref: "python -m pytest -q (408 passed in 3.30s)"
        status: pass
  - id: GATE-02
    description: "Static typing clean across all 11 source files"
    requirement: MODERN-02
    verification:
      - kind: automated
        ref: "python -m mypy src (Success: no issues found in 11 source files)"
        status: pass
  - id: GATE-03
    description: "Linter clean across repository"
    requirement: MODERN-02
    verification:
      - kind: automated
        ref: "python -m ruff check . (All checks passed!)"
        status: pass

---

# Phase 01 Plan 03 Summary: TTY Playback Watchability & Gap Closure

## What Was Done

Plan 01-03 successfully closed UAT Gap 1 (real-TTY playback unwatchable due to scroll-flood and fixed 80-column overflow), restoring watchable terminal playback while preserving exact piped byte-identity:

1. **Dual-Mode `_StdoutSink` & Sizing Seams in `src/main.py`**:
   - Added standard library `import shutil`.
   - Defined terminal control constants `_CLEAR`, `_HOME`, `_HIDE_CURSOR`, `_SHOW_CURSOR`, and `_ANSI_RESET`.
   - Implemented `_stdout_is_tty()` as the single isatty authority.
   - Implemented `_terminal_size()` utilizing `shutil.get_terminal_size((80, 24))`.
   - Implemented `_tty_output_size(config, video_aspect)` performing aspect-fit calculation bounded by terminal dimensions, returning `None` when stdout is not a TTY.
   - Enhanced `_StdoutSink` to emit in-place cursor-home animations on TTY (with initial clear and cursor-hide, plus idempotent `restore()`), while maintaining exact `frame_string + "\n"` plain-text output on pipes with zero escape bytes.
   - Added `refresh_size()`, `output_size()`, and `clear()` to `_StdoutSink` to implement the live duck-typed resize protocol.

2. **Hermetic Test Suite (`tests/test_tty_sink.py`)**:
   - Created 21 unit and integration tests verifying TTY end-to-end execution, piped byte-identity, sizing math (width-limited 16:9, portrait 9:16, aspect defaults, degenerate (1,1) size, multi-aspect boundary bounds), live-resize detection, and restore idempotence.

3. **Quality Gates & Review Disposition**:
   - 408 tests passing in `pytest` (up from 387).
   - Zero issues found in `mypy` across 11 source files.
   - Zero issues found in `ruff`.
   - Triaged all 8 code-review findings in `01-REVIEW-DISPOSITION.md`: marked `IN-03` as fixed and recorded deferred status for `WR-01`–`WR-04` and `IN-01`, `IN-02`, `IN-04`.
