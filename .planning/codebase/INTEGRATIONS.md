---
last_mapped_commit: a55586b3cdf529951d93b522083233d43fa80a2e
last_mapped_at: 2026-11-16
---
# External Integrations

**Analysis Date:** 2026-11-16

## APIs & External Services

**Multimedia CLI Tooling (Native Subprocesses):**
- **FFmpeg (`ffmpeg`):**
  - Used for: Reading video files, demuxing containers, decoding video streams into uncompressed RGB24 pixel streams output to `stdout` (`-f rawvideo -pix_fmt rgb24`).
  - Invocation: Launched as a `subprocess.Popen` in `src/video.py` (`FFmpegFrameReader.open`).
  - Error diagnostics: Errors and container warnings captured via a seekable temporary file (`tempfile.NamedTemporaryFile`) on `stderr` to prevent pipe deadlocks.
- **FFplay (`ffplay`):**
  - Used for: Audio playback directly through speaker output synchronized with the master timeline (`-vn -nodisp -autoexit -stats -loglevel warning`).
  - Invocation: Launched as a `subprocess.Popen` in `src/audio.py` (`AudioPlayer.start`).
  - Status stream: Background daemon thread (`_stats_thread`) monitors `stderr` for real-time `A-V` presentation drift and media clock timestamps.
- **FFprobe (`ffprobe`):**
  - Used for: Pre-flight stream probing without decoding. Checks for presence of audio streams (`-select_streams a`), source frame rates (`r_frame_rate`, `avg_frame_rate`), video resolution (`width`, `height`), and container duration.
  - Invocation: Synchronous inspection via `subprocess.run` in `src/audio.py` (`detect_audio_status`) and `src/sync.py` (`probe_video_rate`, `probe_video_size`, `probe_media_duration`).

**Remote Web Services / REST APIs:**
- None. The application operates entirely locally on local media files and does not connect to external networks.

## Data Storage

**Databases:**
- None.

**File Storage:**
- **Local Filesystem:**
  - Reads local video media files supplied via CLI arguments (`src/main.py`).
  - Creates temporary files via `tempfile.NamedTemporaryFile` in `src/video.py` for stderr buffering of decoder logs. Cleaned up on reader close.
- **Test Assets:**
  - `assets/` directory (historical demo video clips / sample media).

**Caching:**
- In-memory only:
  - `src/renderer.py`: `_char_table_cache` dictionary caches 256-byte ASCII lookup tables per gradient.
  - `src/renderer.py`: `@lru_cache(maxsize=None)` caches `_box_ranges(src_size, dst_size)` partitions for fast area-averaging re-scaling calculations.

## Authentication & Identity

**Auth Provider:**
- None. Standalone local command-line application; no authentication or authorization required.

## Monitoring & Observability

**Error Tracking:**
- Local exception handling with typed errors: `FFmpegNotFoundError`, `FFmpegDecodeError`, `FFplayNotFoundError`, `FFplayPlaybackError`.
- Clean terminal teardown on `KeyboardInterrupt` (SIGINT) or EOF in `src/main.py` (`run`), ensuring cursor visibility and ANSI reset are restored.

**Logs & Diagnostics:**
- Diagnostic reports written to `sys.stderr` when debug mode is enabled via `--debug` or `RGB_ASCII_DEBUG=1`.
- Metrics include:
  - Timing statistics (`FrameClock.report()` in `src/timing.py`): target FPS, achieved FPS, frame duration, avg processing ms, avg pacing ms, lateness metrics.
  - Dropped frames & lag recovery (`FrameSelector.stats.report()` in `src/framesel.py`).
  - Temporal smoothing status (`TemporalSmoother` in `src/smoothing.py`).
  - Audio playback & A/V drift stats (`PlaybackTimeline` in `src/sync.py`).
  - Adaptive quality status (`QualityController` in `src/adaptive.py`).

## CI/CD & Deployment

**Hosting & Distribution:**
- Open-source repository hosted on GitHub: `https://github.com/Sujoy-004/ASCII`.
- Packaged as a standard PEP 517/621 wheel / source distribution via `pyproject.toml`.
- Console entry point `rgb-ascii` created during `pip install .`.

**CI Pipeline:**
- **GitHub Actions (`.github/workflows/ci.yml`):**
  - Runs on `push` to `main`, `pull_request`, and `workflow_dispatch`.
  - Matrix testing: `ubuntu-latest` and `windows-latest` across Python `3.10` and `3.13`.
  - Stages:
    1. Byte-compile sources: `python -m compileall -q src`
    2. Import validation: dynamic import check across all modules in `src/`
    3. Unit & integration test execution: `python -m pytest -q`
    4. Type checking: `python -m mypy`
    5. Code linting: `python -m ruff check .`
    6. Performance smoke benchmark: `python bench.py --repeat 1 --sizes 8x4 --src 8x4`

## Environment Configuration

**Required Environment Variables:**
- None. All settings have sensible zero-configuration defaults.

**Optional Environment Flags (`src/main.py`):**
- `RGB_ASCII_NO_ADAPTIVE` - Disables adaptive quality load-shedding.
- `RGB_ASCII_HALF_BLOCK` - Enables half-block rendering mode.
- `RGB_ASCII_NO_COLOR` - Forces monochrome output.
- `RGB_ASCII_NO_AUDIO` - Disables audio track playback.
- `RGB_ASCII_SMOOTHING` - Sets smoothing alpha factor (0.0 to 1.0).
- `RGB_ASCII_FPS` - Forces target playback frame rate.
- `RGB_ASCII_PRESET` - Selects character set preset (`default`, `dense`, `simple`, `blocks`).
- `RGB_ASCII_CHARS` - Sets raw character gradient string.
- `RGB_ASCII_DEBUG` - Enables debug reporting to stderr.

**Secrets Location:**
- None. No API keys, credentials, or secrets are used or required by this project.

## Webhooks & Callbacks

**Incoming:**
- None.

**Outgoing:**
- None.

---

*Integration audit: 2026-11-16*
