---
last_mapped_commit: a55586b3cdf529951d93b522083233d43fa80a2e
last_mapped_at: 2026-11-16
---
<!-- refreshed: 2026-11-16 -->
# Architecture

**Analysis Date:** 2026-11-16

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             CLI Entry Point                                 │
│                               `src/main.py`                                 │
├──────────────────────────────┬──────────────────────────────────────────────┤
│       Probing & Config       │            Process Coordination              │
│  `src/config.py`, `src/sync` │       `src/video.py`, `src/audio.py`         │
└──────────────┬───────────────┴──────────────────────┬───────────────────────┘
               │                                      │
               ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Synchronization & Timing                           │
│     `src/sync.py` (PlaybackTimeline)  ◄──►  `src/timing.py` (FrameClock)     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Frame Selection & Conditioning                        │
│   `src/framesel.py` (FrameSelector)  ──►  `src/smoothing.py` (Smoother)    │
│                        ▲                                                    │
│                        │ (Load shedding feedback)                           │
│               `src/adaptive.py` (QualityController)                         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Rendering & Presentation                          │
│   `src/renderer.py` (RGBAsciiRenderer) ──► `src/terminal.py` (Terminal)     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI & Pipeline Orchestrator | Parses arguments/env, initializes components, drives main playback loop, cleans up resources | `src/main.py` |
| Runtime Configuration | Defines `Config` dataclass and character presets; validates options | `src/config.py` |
| Video Decoding | Spawns FFmpeg subprocess, requests RGB24 raw video pipe on stdout, handles errors | `src/video.py` |
| Audio Playback | Spawns FFplay subprocess in headless mode, tracks playback status and audio clock | `src/audio.py` |
| Playback Timeline & Sync | Manages shared master timeline, probed video/audio properties, and natural exit policy | `src/sync.py` |
| Frame Clock & Timing | Paces playback against absolute deadlines on monotonic clock or adopted media clock | `src/timing.py` |
| Frame Selection | Drains FFmpeg pipe without backpressure; drops stale frames when behind deadline | `src/framesel.py` |
| Temporal Smoothing | Exponential blend of consecutive displayed frames in RGB24 space to reduce flicker | `src/smoothing.py` |
| Adaptive Quality Controller | Monitors per-frame render work; sheds smoothing or color during sustained overruns | `src/adaptive.py` |
| ASCII & ANSI Renderer | Maps RGB24 pixels to luminance and ASCII characters; formats 24-bit True Color ANSI | `src/renderer.py` |
| Terminal Controller | Queries terminal size, manages viewport aspect ratio, writes buffered frames to stdout | `src/terminal.py` |

## Pattern Overview

**Overall:** Decoupled Pipe-and-Filter architecture driven by an authoritative Master Timeline Clock.

**Key Characteristics:**
- **Zero Third-Party Runtime Dependencies:** Leverages Python's standard library and OS subprocesses for streaming video/audio.
- **Pipelined Subprocesses via Uncompressed Pipes:** FFmpeg decodes directly into memory via raw RGB24 frames on standard output, eliminating intermediate disk storage.
- **Non-Accumulating Absolute Deadline Scheduling:** Frame deadlines are anchored to an absolute playback origin (`deadline = start + target_media_time(N)`) rather than relative sleep chains, preventing frame drift.
- **Drained Non-Blocking Frame Dropping:** The video decoder pipe is read continuously; frames that become stale due to render lateness are dropped immediately rather than queued or backpressured into FFmpeg.
- **Graceful Multi-Stage Quality Degradation:** If host processing capacity falls behind the frame budget, `QualityController` adaptively disables temporal smoothing, followed by ANSI color formatting, preserving frame pacing over visual fidelity.

## Layers

**Orchestration Layer:**
- Purpose: CLI interface, parameter validation, lifecycle management, and main loop coordination.
- Location: `src/main.py`
- Contains: `main()`, `run()`, `config_from_args()`, and diagnostic reporting routines.
- Depends on: All lower layers (`src.config`, `src.video`, `src.audio`, `src.sync`, `src.timing`, `src.framesel`, `src.smoothing`, `src.adaptive`, `src.renderer`, `src.terminal`).

**Subprocess & Media I/O Layer:**
- Purpose: Interface with system multimedia binaries (`ffmpeg`, `ffplay`, `ffprobe`).
- Location: `src/video.py`, `src/audio.py`
- Contains: `FFmpegFrameReader`, `AudioPlayer`, and stream status detectors.
- Depends on: External CLI executables, `src.sync`.
- Used by: `src/main.py`.

**Timeline & Synchronization Layer:**
- Purpose: Pacing, clock tracking, and synchronization between independent audio and video streams.
- Location: `src/sync.py`, `src/timing.py`
- Contains: `PlaybackTimeline`, `FrameClock`, `TimestampStream`, and completion timeout algorithms.
- Used by: `src/main.py`, `src/framesel.py`.

**Frame Conditioning & Processing Layer:**
- Purpose: Real-time lag recovery, frame skipping, exponential smoothing, and load adaptation.
- Location: `src/framesel.py`, `src/smoothing.py`, `src/adaptive.py`
- Contains: `FrameSelector`, `TemporalSmoother`, `QualityController`.
- Used by: `src/main.py`.

**Transformation & Output Layer:**
- Purpose: Translating raw pixel buffers into ANSI strings and writing to terminal viewport.
- Location: `src/renderer.py`, `src/terminal.py`
- Contains: `RGBAsciiRenderer`, `resize_rgb24_area`, `char_table_for`, `TerminalRenderer`.
- Used by: `src/main.py`, `bench.py`.

## Data Flow

### Primary Video Playback Flow

1. **Invocation & Pre-flight:**
   - User invokes `rgb-ascii video.mp4` or `python -m src.main video.mp4` (`src/main.py:main`).
   - `src/main.py` builds `Config`, queries `TerminalRenderer.output_size()`, probes video frame rate/size/duration via `ffprobe`, and checks audio presence.
2. **Process Launch & Priming:**
   - `AudioPlayer.start()` launches FFplay in background (`src/audio.py`).
   - `FFmpegFrameReader.open()` launches FFmpeg decoding to RGB24 pipe (`src/video.py`).
   - `FrameSelector.prime()` reads Frame 0 *before* playback start to absorb process spawn latency (`src/framesel.py:84`).
3. **Timeline Initiation:**
   - `FrameClock.start()` captures monotonic `start_time` (`src/timing.py:126`).
   - If FFplay audio clock is ready, `FrameClock.adopt_media_clock()` syncs clock basis (`src/timing.py:176`).
4. **Per-Frame Processing Loop (`src/main.py:run`):**
   - `FrameSelector.next()` reads next frame from FFmpeg; drops stale frames if deadline for next slot has already passed (`src/framesel.py:101`).
   - Terminal geometry refreshed; resized if changed (`src/terminal.py:refresh_size`).
   - `TemporalSmoother.smooth()` applies optional RGB24 alpha blend (`src/smoothing.py:72`).
   - `RGBAsciiRenderer.render_frame()` converts RGB24 to ANSI True Color ASCII string (`src/renderer.py:257`).
   - `TerminalRenderer.write_frame()` writes frame buffer to stdout (`src/terminal.py:105`).
   - `FrameClock.sleep_until_deadline()` pauses execution for remaining frame duration budget (`src/timing.py:257`).
   - `QualityController.update()` assesses execution utilization and shifts quality levels if needed (`src/adaptive.py:82`).
5. **Teardown:**
   - Video EOF detected (`frame is None`).
   - Audio natural exit waited up to `audio_completion_timeout` (`src/sync.py:103`).
   - Subprocesses terminated, terminal cursor restored, and diagnostics printed if `--debug` (`src/main.py:532`).

## Key Abstractions

**`FrameClock` (`src/timing.py`):**
- Pacing engine that schedules each frame at `playback_start + target_media_time(N)`.
- Handles switching between monotonic clock and FFplay's reported audio clock seamlessly with time rebasing.

**`PlaybackTimeline` (`src/sync.py`):**
- Unified observation recorder tracking video launch, audio launch, first frame, video EOF, audio exit, and max A/V drift.

**`FrameSelector` (`src/framesel.py`):**
- Real-time rate adapter. Keeps decoder pipe flowing, evaluating each frame against current clock to discard already-obsolete frames before rendering.

**`RGBAsciiRenderer` (`src/renderer.py`):**
- Core graphics engine. Implements Rec. 601 luminance weighting (`0.299*R + 0.587*G + 0.114*B`), precomputed character lookup tables, area-averaging re-scaling, and half-block character rendering.

## Entry Points

**Console Script:**
- Name: `rgb-ascii`
- Definition: `pyproject.toml: [project.scripts] rgb-ascii = "src.main:main"`
- Entry function: `src/main.py:main()`

**Module Invocation:**
- Command: `python -m src.main <path_to_video>`
- Entry function: `src/main.py:main()` via `if __name__ == "__main__": main()`

**Benchmark Harness:**
- Command: `python bench.py [options]`
- Entry function: `bench.py:main()`

## Architectural Constraints

- **Python Standard Library Only:** No external pip packages permitted at runtime.
- **External Dependency Requirement:** Host system must have `ffmpeg` (and optionally `ffplay`/`ffprobe`) installed on `PATH`.
- **Single-Threaded Render Pipeline:** Video decoding and terminal rendering run on the main process thread; audio runs in a separate FFplay process, with a light daemon thread only reading FFplay's stderr stats.
- **Memory Boundedness:** No unbounded frame buffering. Raw frame reads are immediately rendered or dropped.

## Anti-Patterns

### Chained Sleep Delay (`time.sleep(1/fps)`)
**What happens:** Sleeping for a fixed duration after rendering each frame.
**Why it's wrong:** Render and decode times accumulate, leading to severe playback lag and desynchronization with audio.
**Do this instead:** Schedule each frame against an absolute deadline on a monotonic timeline (`FrameClock.sleep_until_deadline` in `src/timing.py`).

### Backpressuring FFmpeg on Lag
**What happens:** Halting reads from FFmpeg stdout when the renderer is behind schedule.
**Why it's wrong:** FFmpeg buffers fill up, pipe blocks, and subsequent reads deliver heavily delayed stale frames.
**Do this instead:** Continuously read and drain all decoded frames, discarding stale frames immediately (`FrameSelector` in `src/framesel.py`).

### String-Blending Escape Codes
**What happens:** Attempting to interpolate or smooth ANSI-escaped terminal strings.
**Why it's wrong:** Corrupts escape sequences, leading to visual glitches and terminal artifacts.
**Do this instead:** Perform temporal smoothing strictly on numeric RGB24 byte buffers before ASCII/ANSI conversion (`TemporalSmoother` in `src/smoothing.py`).

## Error Handling

**Strategy:** Clean degradation and fail-fast with actionable guidance on missing dependencies.
- `FFmpegNotFoundError` / `FFplayNotFoundError`: Intercepted with helpful platform-specific installation instructions (links to official downloads and PATH configuration tips).
- Decode Termination Classification: `classify_decode_termination` in `src/video.py` analyzes stderr logs to distinguish benign EOF or recoverable decoder packet drops from fatal container corruptions (e.g., missing MOOV atom, partial files).
- Defensive Terminal Restoration: `src/main.py:run` wraps playback in `try...finally` to ensure the cursor is unhidden and ANSI attributes reset even on unexpected crashes or user interrupts.

## Cross-Cutting Concerns

- **Logging & Diagnostics:** Centralized under `Config.debug`, printed cleanly to `sys.stderr` without polluting standard output video stream.
- **Terminal Resize Handling:** `TerminalRenderer.refresh_size()` dynamically detects terminal window resizing, triggering automatic viewport recalculation and clean redraws without resetting media playback.
- **Platform Portability:** Handles OS-specific newline conventions, terminal escape compatibility (ANSI True Color), and Windows console behavior.

---

*Architecture analysis: 2026-11-16*
