---
status: testing
phase: 01-codebase-modernization-core-engine-extraction
source: [01-VERIFICATION.md]
started: 2026-11-17T01:00:46Z
updated: 2026-11-17T01:00:46Z
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
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
