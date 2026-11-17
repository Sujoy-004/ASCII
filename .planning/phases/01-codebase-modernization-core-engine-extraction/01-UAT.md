---
status: testing
phase: 01-codebase-modernization-core-engine-extraction
source: [01-VERIFICATION.md]
started: 2026-11-17T01:00:46Z
updated: 2026-11-17T01:31:22Z
---

## Current Test

number: 1
name: Real-media headless CLI playback
expected: |
  Run the headless CLI against a real media file with FFmpeg installed:
  `python -m src.main <video>` (or `rgb-ascii <video>`). Observe stdout, then
  Ctrl+C partway through. Plain-text ASCII frames stream to stdout with no ANSI
  cursor/escape sequences; Ctrl+C exits cleanly without orphaned FFmpeg/FFplay
  processes.
awaiting: user response

## Tests

### 1. Real-media headless CLI playback
expected: Run `python -m src.main <video>` (or `rgb-ascii <video>`) with FFmpeg installed. Observe stdout, then Ctrl+C partway through. Plain-text ASCII frames stream to stdout with no ANSI cursor/escape sequences; Ctrl+C exits cleanly without orphaned FFmpeg/FFplay processes.
result: [issues]
notes: |
  Run 2026-11-17 with `python -m src.main C:\Users\KIIT0001\Videos\mha.mp4`
  (Python 3.11.8, PowerShell, FFmpeg installed).
  PASSED: plain-text ASCII frames streamed to stdout; no ANSI cursor/escape
  sequences in the stream; Ctrl+C exited cleanly ("Interrupted by user.
  Exiting cleanly."); no orphaned ffmpeg/ffplay processes (verified via
  Get-Process after exit).
  FAILED (watchability): frames stream blind. The phase replaced per-frame
  terminal-size polling (old code: terminal.output_size(video_aspect) with
  in-place redraw from src/terminal.py) with a fixed 80-column aspect grid
  (main.py:674 _headless_output_size), and _StdoutSink (main.py:88) writes
  frame+"\n" with no cursor repositioning. On a real terminal each frame
  overflows the window and floods scroll — user reported "only the audio
  loads, the video is broken."
  DECISION: gap-fix approach A approved — TTY-fit via shutil.get_terminal_size
  plus isatty-guarded cursor-home animation; piped/redirected output stays
  byte-identical plain text.

## Summary

total: 1
passed: 0
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

### Gap 1: Real-TTY playback unwatchable (fixed grid overflows, no in-place redraw)
- Symptom: audio plays; ASCII floods the terminal with scroll on every frame; unwatchable.
- Root cause: main.py:674 sizes from _headless_output_size (fixed 80 cols, aspect-derived rows, no terminal query); the terminal module's output_size polling and cursor redraw were removed in this phase.
- Approved fix (user decision 2026-11-17): Option A — TTY-aware sizing via shutil.get_terminal_size + isatty-guarded cursor animation; piped/redirected output unchanged.

## Deferred Follow-Ups

- `rgb-ascii` console script broken in this environment: stale editable install (pip metadata: Editable project location C:\Users\KIIT0001\Documents\antigravity skills\ASCII — deleted). ModuleNotFoundError: No module named 'src'. User decision: keep `python -m src.main <video>` as the entry point; no reinstall requested. Repo packaging config (pyproject.toml packages=["src"], project.scripts) is correct.
