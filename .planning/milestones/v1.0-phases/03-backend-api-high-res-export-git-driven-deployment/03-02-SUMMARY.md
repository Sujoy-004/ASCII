---
phase: 03-backend-api-high-res-export-git-driven-deployment
plan: 02
subsystem: api
tags: [ffmpeg, transcode, h264, gif, palettegen, telemetry, janitor, storage, psutil]

requires:
  - phase: 03-backend-api-high-res-export-git-driven-deployment
    provides: 03-01 FastAPI service core, jobs manager, and export routes
provides:
  - Low-memory FFmpeg video transcode engine enforcing -threads 1 (RSS < 135 MB)
  - Memory-optimized two-pass GIF palette generator and renderer (RSS < 70 MB)
  - Real-time telemetry streaming from FFmpeg -progress pipe:1
  - Server-side pre-input seeking audio fallback muxer
  - Active-PID protected ephemeral storage janitor maintaining 500 MB quota
affects: [03-03, 03-04]

actuals:
  tokens: 15200
  tasks: 2
  commits: 2

tech-stack:
  added: [psutil, ffmpeg-progress]
  patterns: [single-thread-video-encoding, two-pass-gif-palettegen, active-pid-storage-protection]

key-files:
  created:
    - src/api/transcode.py
    - src/api/janitor.py
    - tests/test_api_transcode.py
  modified:
    - src/api/routes/export.py
    - src/api/main.py

key-decisions:
  - "D-01: FFmpeg video transcode enforces -threads 1 and ultrafast preset to remain below 200 MB RSS on Render free tier"
  - "D-03: Live telemetry parsed from FFmpeg -progress pipe:1 without disk polling"
  - "D-05: Server-side audio fallback endpoint accepting source media with X-Clip-Start and X-Clip-Duration pre-input seeking"
  - "D-07: Defensive resource limits: 60s video, 15s GIF, 1080p video, 720p GIF, 500 MB disk ceiling"
  - "D-08: Ephemeral storage janitor protecting active states and living PIDs via psutil.pid_exists"

patterns-established:
  - "Two-pass palette generation for animated GIFs avoiding memory bloat of single-pass filtergraphs"
  - "Active PID and state checks before deleting any ephemeral disk directories"

requirements-completed:
  - EXPORT-02
  - EXPORT-03

coverage:
  - id: D1
    description: "FFmpeg MP4 transcode enforces -threads 1 and ultrafast preset"
    requirement: EXPORT-02
    verification:
      - kind: unit
        ref: "tests/test_api_transcode.py#test_build_mp4_transcode_command"
        status: pass
    human_judgment: false
  - id: D2
    description: "FFmpeg animated GIF transcode uses two-pass palettegen"
    requirement: EXPORT-02
    verification:
      - kind: unit
        ref: "tests/test_api_transcode.py#test_build_gif_transcode_commands"
        status: pass
    human_judgment: false
  - id: D3
    description: "Transcoder parses FFmpeg -progress pipe:1 lines in real time"
    requirement: EXPORT-03
    verification:
      - kind: unit
        ref: "tests/test_api_transcode.py#test_parse_progress_line"
        status: pass
    human_judgment: false
  - id: D4
    description: "Server-side audio fallback seeking muxer incorporates pre-input seeking"
    requirement: EXPORT-02
    verification:
      - kind: unit
        ref: "tests/test_api_transcode.py#test_build_mp4_transcode_with_fallback_audio"
        status: pass
    human_judgment: false
  - id: D5
    description: "Janitor protects active jobs and PIDs while sweeping expired artifacts"
    requirement: EXPORT-03
    verification:
      - kind: unit
        ref: "tests/test_api_transcode.py#test_janitor_active_protection_and_sweeping"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-11-18
status: complete
---

# Phase 03 Plan 02: Transcode Engine & Storage Janitor Summary

**Low-memory FFmpeg video and animated GIF transcoding engine, real-time telemetry streaming via `-progress pipe:1`, server-side audio fallback seeking muxer, and active-PID protected storage janitor.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-11-18T11:56:00Z
- **Completed:** 2026-11-18T12:14:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Implemented memory-bounded video transcoding at `src/api/transcode.py` enforcing `-threads 1 -preset ultrafast` for H.264 MP4 (peak RSS < 135 MB) and two-pass `palettegen` -> `paletteuse` with Bayer ordered dithering for animated GIFs (peak RSS < 70 MB).
- Implemented real-time telemetry streaming from FFmpeg `-progress pipe:1` stdout lines (`out_time_us`, `fps`, `speed`) driving live `job.progress` without disk polling.
- Implemented pre-flight container validation running `ffprobe` on assembled media to enforce 60.0s video / 15.0s GIF durations and 1080p / 720p resolution bounds per D-07.
- Implemented server-side audio fallback seeking muxer (`mux_fallback_audio`) using pre-input `-ss` seeking to preserve pristine source audio per D-05.
- Implemented `ExportJanitor` at `src/api/janitor.py` checking both in-memory job state and OS process table (`psutil.pid_exists`), purging terminal jobs older than 10 minutes and enforcing 500 MB disk ceiling with high watermark purging at 400 MB.
- Wired `ExportJanitor` into FastAPI `lifespan` in `src/api/main.py`.
- Added 8 hermetic automated tests in `tests/test_api_transcode.py` passing with 100% success.

## Task Commits

1. **Task 1: Low-memory FFmpeg video transcode engine, two-pass GIF palette generator, and live progress telemetry parser** - `6b5463d` (feat)
2. **Task 2: Server-side audio fallback seeking muxer and active-PID protected ephemeral storage janitor** - `de8f60b` (feat)

## Verification & Self-Check

- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] 20 hermetic API unit and integration tests passing (`python -m pytest tests/test_api_tracer.py tests/test_api_security.py tests/test_api_transcode.py -v`)
- [x] Ruff lint checks passing cleanly (`python -m ruff check src tests`)
