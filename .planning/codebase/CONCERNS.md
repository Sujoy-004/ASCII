---
last_mapped_commit: a55586b3cdf529951d93b522083233d43fa80a2e
last_mapped_at: 2026-11-16
---
# Codebase Concerns

**Analysis Date:** 2026-11-16

## Tech Debt

**Area Rescaling Cost in Python:**
- Issue: `resize_rgb24_area` in `src/renderer.py` is written in pure Python. While optimized using plane splitting (`r_plane = frame[0::3]`) and contiguous buffer slicing, software downscaling/upscaling during live terminal window resizing still consumes significant CPU time (~30-70 ms per frame on larger terminal resolutions).
- Files: `src/renderer.py`
- Impact: If a user resizes their terminal window to a high resolution during playback, frame rate may momentarily dip and trigger frame drops or adaptive quality downgrades.
- Fix approach: Steady-state playback avoids this because FFmpeg scales directly to the terminal grid dimensions at decode time (`-vf scale=W:H`). Further optimization could cache downscaled lookup indices or offload scaling to C/Rust or a compiled native accelerator if external dependencies are ever permitted.

**Flat Package Layout in `src/`:**
- Issue: `src/` contains 12 modules directly at the package root without sub-packages (`src/video.py`, `src/audio.py`, `src/renderer.py`, etc.).
- Files: `src/`
- Impact: Manageable for a codebase of ~2,500 lines, but as features expand, grouping into domain sub-packages (e.g. `src/media/`, `src/render/`, `src/clock/`) will be needed to preserve architectural boundaries.
- Fix approach: Refactor into sub-packages if additional formatters or decoders are added.

## Known Bugs

**None currently identified in test suite:**
- The repository has 387 passing tests with comprehensive error simulation (corrupt media, truncated streams, missing external binaries, audio desync).
- Historical bugs noted in comments (such as undefined `_QUALITY_NAMES` in debug reports or container decode terminations exiting 0) have been resolved and guarded with regression tests in `tests/test_adaptive.py` and `tests/test_frame_reader.py`.

## Security Considerations

**Subprocess Command Line Execution:**
- Risk: Potential command injection if arbitrary user input were passed unsanitized into shell subprocesses.
- Files: `src/video.py`, `src/audio.py`, `src/sync.py`
- Current mitigation: All subprocess calls use explicit argument lists (`cmd = [self.ffmpeg, ...]`) with `shell=False`. Arguments such as file paths are passed as single distinct argv entries, preventing shell expansion or command chaining.
- Recommendations: Maintain the strict `shell=False` policy on all future process spawning.

**Untrusted Media Handling:**
- Risk: Malformed or malicious media files crafted to exploit vulnerabilities in underlying FFmpeg decoders.
- Files: `src/video.py`, `src/audio.py`
- Current mitigation: FFmpeg runs in an isolated subprocess with stderr diagnostics captured; fatal errors are caught and classified without crashing the Python parent process.
- Recommendations: Keep system FFmpeg updated to the latest security patch release.

## Performance Bottlenecks

**Terminal I/O Bandwidth on Large Windows (True Color ANSI):**
- Problem: ANSI 24-bit True Color requires emitting escape sequences per character (e.g., `\x1b[38;2;255;255;255mX`), resulting in ~20-30 bytes of terminal stream per rendered cell. On full-screen 4K terminals (e.g., 240x80 = 19,200 cells), each frame can produce ~400-500 KB of text output. At 30 FPS, this saturates terminal emulator rendering threads.
- Files: `src/renderer.py`, `src/terminal.py`
- Cause: Terminal emulator throughput limits and ANSI escape formatting overhead.
- Improvement path: Palette optimization / ANSI state diffing: only emit color escape sequences when the color changes between adjacent cells or consecutive frames, or utilize dirty-region updating.

## Fragile Areas

**FFplay Headless Audio Stats Parsing:**
- Files: `src/audio.py`
- Why fragile: FFplay outputs audio playback statistics on `stderr` using interactive text lines (`A-V: -0.012 ...`). Changes in FFplay's stderr output format across major FFmpeg versions could disrupt regex parsing (`_STATS_RE`).
- Safe modification: When modifying `_STATS_RE` or `_stats_thread`, run `tests/test_audio.py` and `tests/test_startup_sync.py` which test varied FFplay status line formatting.
- Test coverage: Well covered by unit tests with mocked stderr streams.

**FFmpeg Passthrough Frame Rate vs Presentation Timestamps:**
- Files: `src/video.py`, `src/sync.py`, `src/timing.py`
- Why fragile: Variable frame rate (VFR) videos decouple frame indices from fixed time intervals. The project relies on `-fps_mode passthrough` and streaming timestamp probing via `ffprobe` to ensure decoded frame counts align with presentation timestamps.
- Safe modification: Any change to FFmpeg command line flags (`-fps_mode`, `-vf scale`) must be verified against `tests/test_timestamp_stream.py` and `tests/test_vfr_tail.py`.

## Scaling Limits

**Maximum Terminal Resolution:**
- Current capacity: Performs smoothly up to ~160x50 cells (standard 1080p full screen or smaller terminal windows) at 30 FPS.
- Limit: Terminals larger than 200x60 cells under pure-Python rendering may experience frame dropping unless `adaptive_quality` is enabled to shed smoothing or color.
- Scaling path: Half-block mode (`RGB_ASCII_HALF_BLOCK=1`) doubles vertical resolution without increasing character cell counts. Further scaling requires dirty-line terminal diffing.

## Dependencies at Risk

**External FFmpeg / FFplay Binaries:**
- Risk: Not installable via Python package managers (`pip`); users must manually install FFmpeg and configure their system `PATH`.
- Impact: If FFmpeg or FFplay is missing or outdated, users encounter `FFmpegNotFoundError` or `FFplayNotFoundError`.
- Migration plan: Clear, platform-specific error messaging is implemented pointing users to official download mirrors (e.g., Gyan builds on Windows, Homebrew on macOS, package managers on Linux).

## Missing Critical Features

**Interactive Playback Controls:**
- Problem: The player currently runs non-interactively from start to EOF (or Ctrl+C to stop). There is no keyboard support for pause, play, seek, volume adjust, or loop during playback.
- Blocks: Rich interactive media player experience.

## Test Coverage Gaps

**Real Terminal Emulator Resizing:**
- What's not tested: While mathematical aspect ratio recalculation and unit tests exist (`tests/test_terminal.py`, `tests/test_sampling.py`), actual OS terminal resize events (e.g., `SIGWINCH` on POSIX or console buffer events on Windows) during live playback rely on polling `shutil.get_terminal_size()`.
- Files: `src/terminal.py`, `src/main.py`
- Risk: Rapid continuous resizing by a user might cause slight visual tearing before the next frame is written.
- Priority: Low.

---

*Concerns audit: 2026-11-16*
