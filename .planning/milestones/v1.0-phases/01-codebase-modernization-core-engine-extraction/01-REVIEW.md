---
phase: 01-codebase-modernization-core-engine-extraction
reviewed: 2026-11-17T06:21:01+05:30
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/__init__.py
  - src/config.py
  - src/main.py
  - tests/test_facade.py
  - tests/test_media_errors.py
  - tests/test_timestamp_stream.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
  necessity: 0
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-11-17T06:21:01+05:30
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the phase's core-engine-extraction deliverables: the new 36-symbol package facade (`src/__init__.py`), the `status_rows` purge (`src/config.py`), the terminal-to-headless-sink decoupling (`src/main.py`), and the three adapted/new test files. Each reviewed file was read in full and cross-checked against all eight modules it calls into (`adaptive`, `audio`, `framesel`, `renderer`, `smoothing`, `sync`, `timing`, `video`) to verify API consistency at the module boundaries. The full suite passes (387 tests, 5.09s); every name in `__all__` resolves; no stale `status_rows` or `src.terminal` references survive in source; the facade import chain is cycle-free.

The decoupling itself is clean — the duck-typed sink plumbing in `run()` is a faithful transformation and the double-guard on `refresh_size`/`output_size` (main.py:460) is a genuine improvement over the old single-guard. The defects found are concentrated at the edges the phase created or touched: an env-var routing inconsistency that contradicts the CLI's own documented leniency contract, unvalidated sink-reported dimensions that the new sink protocol makes reachable, an unhandled broken pipe in the new `_StdoutSink`, and a decoder-failure test whose FFplay assertions cannot fail because no FFplay is ever started.

No structural-findings block was supplied with this review request. Necessity (category 4) was assessed per the necessity-review rubric (reference read): 0 necessity findings — the `getattr(reader, "media_timestamps", None)` seam is exercised by test fakes, the facade's unused-in-repo exports (`resize_rgb24`, `has_audio_stream`, `ScaleDim`, etc.) are the phase plan's explicitly approved D-03 surface, and the broad `ValueError` backstop in `main()` turned out to be reachable (see WR-02), so it is not an impossible-state guard.

## Warnings

### WR-01: Out-of-range `RGB_ASCII_FPS` still suppresses source-rate detection, contradicting the documented "ignored" contract

**File:** `src/main.py:655-663` (with `src/main.py:204-206`)
**Issue:** `config_from_args` applies the env FPS only when it is a positive integer (`src/main.py:204-206`, `if fps is not None and fps > 0`), so `RGB_ASCII_FPS=0` or `-5` leaves `config.fps` at the default 30 — documented as "ignored" (`src/main.py:181-183`: "`RGB_ASCII_FPS=0` ... ignored"). But the VFR/CFR routing in `main()` gates on *presence*, not validity: `if _env_int("RGB_ASCII_FPS") is not None: pacing_fps = float(config.fps)` (`src/main.py:655-657`). A value of `0` is "present", so `probe_video_rate` never runs: a positively-CFR 23.976 fps clip is paced on the 30 fps grid — ~25% fast relative to the FFplay audio clock — even though the invalid FPS override was supposedly ignored. The same file with `RGB_ASCII_FPS=abc` (unparseable → `_env_int` returns `None`) *does* take the CFR path and paces correctly. Two kinds of "invalid" produce different routing, and the out-of-range one silently breaks A/V sync on CFR sources. Verified at runtime: `RGB_ASCII_FPS=0` → `config.fps == 30` while the presence check still short-circuits.
**Fix:**
```python
# parse once, share the gate:
fps_env = _env_int("RGB_ASCII_FPS")
if fps_env is not None and fps_env > 0:
    config.fps = fps_env

# in main():
if fps_env is not None and fps_env > 0:   # same validity gate, not mere presence
    pacing_fps = float(config.fps)
```

### WR-02: `run()` adopts sink-reported output dimensions without validation; a bad size surfaces as a misleading usage error

**File:** `src/main.py:460-466` (effects at `src/main.py:494-500`, `src/main.py:777-791`)
**Issue:** The phase introduces the duck-typed sink protocol, and `run()` trusts whatever `sink.output_size(video_aspect)` returns: `new_width, new_height = output_size(video_aspect)` is adopted unconditionally (`src/main.py:461-463`). A sink returning `(0, 0)` or negative dimensions flows into `render_resized_frame` → `resize_rgb24_area`, which raises `ValueError("frame dimensions must be positive")` (`src/renderer.py:165-171`). That ValueError is then caught by `main()`'s broad backstop (`except ... ValueError` → `return 2`, `src/main.py:777-791`), printing `Error: frame dimensions must be positive` and exiting with the *usage-error* code — indistinguishable from a bad CLI invocation. This also falsifies the backstop comment's own premise (`src/main.py:783-788`: "this only fires for a path added later"): the sink contract makes it fire today. Default dimensions are safe (`_headless_output_size` clamps rows via `max(1, ...)`); only the sink-reported path is unguarded.
**Fix:**
```python
new_width, new_height = output_size(video_aspect)
if new_width > 0 and new_height > 0 and (new_width, new_height) != (current_width, current_height):
    current_width, current_height = new_width, new_height
    ...
# (ignore a malformed size and keep the current/default dimensions)
```

### WR-03: `_StdoutSink` does not handle `BrokenPipeError`, breaking its own pipe-usability promise

**File:** `src/main.py:88-90`
**Issue:** `_StdoutSink.write_frame` does `sys.stdout.write(...)` + `sys.stdout.flush()` with no error handling, and `BrokenPipeError` (an `OSError`) is not in `main()`'s exception tuple (`src/main.py:777-789`). The class docstring states frames leave "as plain text ... so the command stays usable when the output is piped, redirected, or captured" (`src/main.py:83-85`) — but the most common pipe pattern, `python -m src.main video.mp4 | head -1`, closes the read end early: the next `write_frame` raises `BrokenPipeError`, which propagates as a raw traceback after the `finally` cleanup, and Python's shutdown flush adds `Exception ignored in: <_io.TextIOWrapper ...>` noise on stderr. The promised piped-usage mode terminates noisily instead of cleanly.
**Fix:** Treat a closed stdout as a normal end of playback:
```python
def write_frame(self, frame_string: str) -> None:
    try:
        sys.stdout.write(frame_string + "\n")
        sys.stdout.flush()
    except BrokenPipeError:
        raise EOFError("output stream closed")  # or signal run() to stop cleanly
```
(or catch `BrokenPipeError` alongside `OSError`-family in `main()` and map it to a clean exit).

### WR-04: Vacuous FFplay assertions in `test_failure_does_not_leave_ffplay_running` — the named regression is unprotected

**File:** `tests/test_media_errors.py:190-253`
**Issue:** The test's headline claim is that a decoder failure "stops audio immediately rather than draining it" and does not "leave FFplay running". But `run()` never starts FFplay — `audio.start()` exists only in `main()` (`src/main.py:756`; verified by source inspection) — and the test constructs `AudioPlayer(ffplay="ffplay")` without ever calling `start()`, so `audio._process` is `None` for the whole run. Consequences: the `mock.patch("src.audio.subprocess.Popen", ...)` and the `FakeProc` instance (`tests/test_media_errors.py:198-215, 231, 240`) are dead code; `audio.stop()` in `run()`'s finally is a no-op; and both FFplay-specific assertions hold trivially — `audio._process is None` (`:250`) is true regardless of what `run()` does, and `timeline.audio_waited_for_exit is False` (`:251-253`) cannot flip because the natural-exit wait additionally requires `audio.is_running()`, which is always `False` here. If `run()` regressed to orphan or drain a real FFplay on the error path, this test would still pass. The assertions that do bite (reader closed, sink restored, RuntimeError propagates) are fine. This vacuousness predates the phase diff (only the `_headless_output_size` monkeypatch line changed), but it guards exactly the cleanup contract this phase's `run()` refactoring touched, so it belongs in this review.
**Fix:** Start the audio player before `run()` so the assertions exercise real state:
```python
with mock.patch("src.audio.subprocess.Popen", return_value=ffplay), \
        pytest.raises(RuntimeError):
    audio.start(str(tmp_path / "clip.mp4"))   # wire the FakeProc in
    run(reader, RGBAsciiRenderer(config), terminal, FrameClock(1000, sleep_fn=_noop_sleep),
        config, audio, timeline, media_duration=None)
```
then `audio.stop()` must actually terminate (`ffplay.terminated >= 1`) and the `_process is None` assertion becomes meaningful.

## Info

### IN-01: Ctrl+C during `main()`'s startup window produces a raw traceback

**File:** `src/main.py:637-776`
**Issue:** `run()` handles `KeyboardInterrupt` for the playback loop, but the startup sequence in `main()` does not: the probe `subprocess.run` calls (`:643-645`), `timestamp_probe.start()` (`:671`), the first blocking `reader.read_frame()` (`:741`), `timestamp_probe.wait_ready(..., timeout=0.25)` (`:749`), and `audio.wait_for_media_clock()` (`:762`) are all interruptible blocking points outside any KeyboardInterrupt handling — `KeyboardInterrupt` is a `BaseException`, so it bypasses the `except (...)` tuple. A Ctrl+C in the first ~1s yields a Python traceback (after the `finally` cleanup, which does run). The module docstring advertises "handling clean shutdown and Ctrl+C".
**Fix:** Wrap the startup body in `try: ... except KeyboardInterrupt:` sharing the same cleanup/message path as `run()`'s interrupt handling.

### IN-02: Debug reporter reaches into `AudioPlayer` private state

**File:** `src/main.py:301`
**Issue:** `_report_audio` reads `audio._process` directly to report "FFplay started: yes/no". This couples `main.py` to `AudioPlayer`'s internal attribute name; a rename inside `audio.py` silently breaks the debug report (it would raise `AttributeError` from inside the `finally` block, masking the real shutdown).
**Fix:** Add a small public accessor on `AudioPlayer` (e.g. `def is_started(self) -> bool: return self._process is not None`) and use it here.

### IN-03: `_StdoutSink` docstring overclaims "no terminal escape sequences"

**File:** `src/main.py:83-85`
**Issue:** The docstring says frames "leave as plain text with no terminal escape sequences". With the default `enable_color=True` (and half-block mode, where color is mandatory), `RGBAsciiRenderer` emits ANSI SGR sequences on every glyph (`src/renderer.py:252, 296-298`), so piped/captured output contains `\x1b[38;2;...` escapes. The intended distinction (no cursor-positioning/alt-screen control, unlike the retired terminal) is real, but as written the contract is false and a downstream consumer written against it breaks.
**Fix:** Reword, e.g.: "frames leave as rendered text — ANSI True Color sequences included when color is on (`RGB_ASCII_NO_COLOR=1` for pure glyphs), with no cursor positioning or screen control, so the output is pipe-safe."

### IN-04: `main()`-level tests do not isolate sibling `RGB_ASCII_*` environment variables

**File:** `tests/test_media_errors.py:114-115`, `tests/test_timestamp_stream.py:472-474`
**Issue:** These tests deliberately set the env vars they depend on (`RGB_ASCII_NO_AUDIO`, `RGB_ASCII_FPS`, `RGB_ASCII_DEBUG`) but never clear the rest of the family (`RGB_ASCII_HALF_BLOCK`, `RGB_ASCII_NO_COLOR`, `RGB_ASCII_SMOOTHING`, `RGB_ASCII_PRESET`, `RGB_ASCII_CHARS`, `RGB_ASCII_NO_ADAPTIVE`). A developer shell exporting, say, `RGB_ASCII_HALF_BLOCK=1` plus `RGB_ASCII_NO_COLOR=1` makes `config_from_args` raise, `main()` return 2, and the whole file fails with an obscure exit-code assertion — the documented leniency contract can't help because the failure is a combination rejection.
**Fix:** `monkeypatch.delenv(..., raising=False)` the remaining `RGB_ASCII_*` names alongside the ones each test sets (or add a small autouse fixture in a conftest that pins the family to a known baseline).

---

_Structural Findings (fallow): none provided with this review request._

_Necessity (category 4) assessed at standard depth per the necessity-review rubric; count: 0. Notes: the `getattr(reader, "media_timestamps", None)` seam in `run()` is a test seam exercised by fakes (`tests/test_startup_sync.py:68`, `tests/test_cleanup.py:45`, `tests/test_vfr_tail.py:53`), not an impossible-state guard; the facade's repo-unused exports are the phase plan's explicitly approved D-03 surface (01-01-PLAN.md:99-102), so re-classifying them here would re-open an approved decision; and the `ValueError` backstop in `main()` is *reachable* via WR-02, so it is not a necessity finding._

_Reviewed: 2026-11-17T06:21:01+05:30_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
