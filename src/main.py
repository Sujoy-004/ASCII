"""Entry point: continuous RGB ASCII video rendering with A/V synchronization.

Decodes frames from the input video via FFmpeg, converts each to an
ANSI-colored ASCII frame, writes it to the terminal, and paces playback toward
a target FPS on a shared master playback timeline shared with FFplay audio.
Runs until EOF, handling clean shutdown and Ctrl+C.

The video schedule and the FFplay audio process reference the same
``playback_start`` on the same monotonic clock. Video/audio completion are
tracked separately and an end-of-playback policy lets FFplay finish naturally
instead of being cut off at video EOF.
"""

from __future__ import annotations

import argparse
import os
import sys

from src.audio import (
    AudioPlayer,
    FFplayNotFoundError,
    detect_audio_status,
)
from src.config import CHAR_PRESETS, Config
from src.framesel import FrameSelector
from src.renderer import RGBAsciiRenderer
from src.smoothing import TemporalSmoother
from src.sync import (
    AudioStatus,
    PlaybackTimeline,
    audio_completion_timeout,
    probe_media_duration,
    probe_video_size,
)
from src.terminal import TerminalRenderer
from src.timing import FrameClock
from src.video import FFmpegFrameReader, FFmpegNotFoundError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description=(
            "Play a video as real-time colored ASCII art in the terminal, "
            "with the source audio playing alongside."
        ),
    )
    parser.add_argument(
        "video",
        help="Path to the video file to play (anywhere on the machine; "
             "relative, absolute, or with spaces).",
    )
    return parser


def _env_bool(name: str) -> bool:
    """Return True when the named env var is set to a truthy value."""
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip().lower() not in ("", "0", "false", "no", "off")


def _env_float(name: str, default: float | None = None) -> float | None:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str) -> int | None:
    value = os.environ.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def config_from_args(args: argparse.Namespace) -> Config:
    """Build a Config from the CLI (options come from _RGB_ASCII_* env vars).

    The public command is simply ``python -m src.main VIDEO`` — everything is
    auto-detected at runtime. The internal ``RGB_ASCII_*`` environment
    variables remain available for development/testing without exposing a
    complex public CLI.
    """
    config = Config()

    preset = os.environ.get("RGB_ASCII_PRESET")
    if preset in CHAR_PRESETS:
        config.preset = preset
        config.chars = CHAR_PRESETS[preset]
    chars = os.environ.get("RGB_ASCII_CHARS")
    if chars:
        config.chars = chars
        config.preset = None

    fps = _env_int("RGB_ASCII_FPS")
    if fps is not None and fps > 0:
        config.fps = fps

    smoothing = _env_float("RGB_ASCII_SMOOTHING")
    if smoothing is not None:
        config.smoothing = smoothing

    if _env_bool("RGB_ASCII_NO_COLOR"):
        config.enable_color = False
    if _env_bool("RGB_ASCII_NO_AUDIO"):
        config.enable_audio = False
    if _env_bool("RGB_ASCII_DEBUG"):
        config.debug = True

    return config


def _fmt(value: float | None) -> str:
    """Format an optional offset/duration in seconds for debug output."""
    return "n/a" if value is None else f"{value * 1000:.1f} ms"


def _report_stats(clock: FrameClock) -> None:
    """Print playback timing metrics to stderr (only used in debug mode)."""
    r = clock.report()
    print("Timing:", file=sys.stderr)
    print(f"  Target FPS:      {r['target_fps']:.2f}", file=sys.stderr)
    print(f"  Frame duration:  {r['frame_duration_ms']:.3f} ms", file=sys.stderr)
    print(f"  Frames:          {r['frame_count']}", file=sys.stderr)
    print(f"  Elapsed:         {r['elapsed_s']:.2f} s", file=sys.stderr)
    print(f"  Achieved FPS:    {r['achieved_fps']:.2f}", file=sys.stderr)
    print(f"  Avg processing:  {r['avg_processing_ms']:.2f} ms", file=sys.stderr)
    print(f"  Avg pacing:      {r['avg_pacing_ms']:.2f} ms", file=sys.stderr)
    print(f"  Avg lateness:    {r['avg_lateness_ms']:.2f} ms", file=sys.stderr)
    print(f"  Max lateness:    {r['max_lateness_ms']:.2f} ms", file=sys.stderr)
    print(f"  Late frames:     {r['late_frames']}", file=sys.stderr)
    print(f"  On-time frames:  {r['on_time_frames']}", file=sys.stderr)


def _report_frames(selector: FrameSelector) -> None:
    """Print frame-decoding/dropping metrics (only used in debug mode)."""
    s = selector.stats
    print("Frames:", file=sys.stderr)
    print(f"  Decoded:          {s.decoded}", file=sys.stderr)
    print(f"  Rendered:         {s.rendered}", file=sys.stderr)
    print(f"  Dropped:          {s.dropped}", file=sys.stderr)
    print(f"  Drop rate:        {s.drop_rate:.1f}%", file=sys.stderr)
    print(f"  Catch-up events:  {s.caught_up_events}", file=sys.stderr)
    print(f"  Max burst dropped:{s.max_burst_dropped}", file=sys.stderr)


def _report_smoothing(smoother: TemporalSmoother) -> None:
    """Print temporal-smoothing status (only used in debug mode)."""
    print("Smoothing:", file=sys.stderr)
    print(f"  Enabled:          {'yes' if smoother.enabled else 'no'}", file=sys.stderr)
    print(f"  Alpha:            {smoother.alpha:.2f}", file=sys.stderr)
    print(f"  Representation:   RGB (luminance/ASCII derived)", file=sys.stderr)
    print(f"  Smoothed frames:  {smoother.smoothed_frames}", file=sys.stderr)


def _report_audio(
    config: Config,
    audio: AudioPlayer | None,
    audio_status: AudioStatus,
) -> None:
    """Print audio diagnostics to stderr (only used in debug mode)."""
    if not config.enable_audio:
        print("Audio enabled:        no", file=sys.stderr)
        return
    print("Audio enabled:        yes", file=sys.stderr)
    print(
        f"FFplay available:      {'yes' if audio and audio.ffplay else 'no'}",
        file=sys.stderr,
    )
    print(f"Audio status:         {audio_status.value}", file=sys.stderr)
    print(
        f"FFplay started:        {'yes' if audio and audio._process else 'no'}",
        file=sys.stderr,
    )
    print(
        f"FFplay exited:         {'yes' if audio and not audio.is_running() else 'no'}",
        file=sys.stderr,
    )


def _report_sync(timeline: PlaybackTimeline | None) -> None:
    """Print A/V synchronization diagnostics (only used in debug mode)."""
    if timeline is None:
        return
    t = timeline
    print("Sync:", file=sys.stderr)
    print(
        f"  Audio startup offset: {_fmt(t.audio_startup_offset)} (after playback start)",
        file=sys.stderr,
    )
    print(
        f"  Video first-frame:    {_fmt(t.video_startup_offset)} (after playback start)",
        file=sys.stderr,
    )
    print(
        f"  Video EOF:            {_fmt(None if t.video_eof_at is None else t.video_eof_at - t.playback_start)} (after playback start)",
        file=sys.stderr,
    )
    print(
        f"  Audio exit:           {_fmt(None if t.audio_exit_at is None else t.audio_exit_at - t.playback_start)} (after playback start)",
        file=sys.stderr,
    )
    print(
        f"  Completion offset:    {_fmt(t.completion_offset)} (audio tail past video EOF)",
        file=sys.stderr,
    )
    print(
        f"  Audio waited to exit: {'yes' if t.audio_waited_for_exit else 'no'}",
        file=sys.stderr,
    )


def run(
    reader,
    renderer,
    terminal,
    clock: FrameClock,
    config: Config,
    audio: AudioPlayer | None = None,
    timeline: PlaybackTimeline | None = None,
    media_duration: float | None = None,
    video_aspect: float | None = None,
) -> int:
    """Run the continuous playback loop, cleaning up on EOF and Ctrl+C.

    Returns 0. Owns the try/finally cleanup so terminal state, the FFmpeg
    process, and the FFplay audio process are always restored regardless of
    how playback ends.

    Each frame is scheduled against an absolute timeline deadline provided by
    the FrameClock; processing time is recorded separately from presentation.

    End-of-playback policy (M5):
      - On normal video EOF, if FFplay is still (legitimately) running, wait
        for it to exit naturally within a timeline-derived bound so the
        remaining audio is NOT arbitrarily cut off.
      - On interrupt/error, stop audio immediately (user wants out now).
      - In all cases ``audio.stop()`` runs as a final guarantee, and FFplay is
        never left orphaned.
    """
    interrupted = False
    normal_eof = False
    clock.start(timeline.playback_start if timeline is not None else None)
    selector = FrameSelector(reader, clock)
    smoother = TemporalSmoother(config)
    current_width, current_height = reader.width, reader.height
    try:
        while True:
            frame, src_index = selector.next()
            if frame is None:
                normal_eof = True
                break

            # Re-check the terminal on every presentation cycle. A resize only
            # changes rendering dimensions; the decoded frame source and the
            # absolute playback timeline continue uninterrupted.
            refresh_size = getattr(terminal, "refresh_size", None)
            if refresh_size is not None and refresh_size():
                new_width, new_height = terminal.output_size(video_aspect)
                if (new_width, new_height) != (current_width, current_height):
                    current_width, current_height = new_width, new_height
                    clear = getattr(terminal, "clear", None)
                    if clear is not None:
                        clear()

            frame = smoother.smooth(frame)  # M7 visual smoothing (pass-through when off)
            proc_start = clock.current_time()
            if (current_width, current_height) == (reader.width, reader.height):
                ascii_frame = renderer.render_frame(frame, reader.width, reader.height)
            else:
                ascii_frame = renderer.render_resized_frame(
                    frame,
                    reader.width,
                    reader.height,
                    current_width,
                    current_height,
                )
            terminal.write_frame(ascii_frame)
            clock.wait_until(clock.deadline(src_index), proc_start)
            if selector.stats.rendered == 1 and timeline is not None:
                timeline.first_frame_at = clock.current_time()
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if timeline is not None:
            timeline.video_eof_at = clock.current_time()
            timeline.frame_count = selector.stats.rendered
        if config.debug and audio is not None:
            _report_audio(
                config,
                audio,
                timeline.audio_status if timeline is not None else AudioStatus.ABSENT,
            )
        reader.close()
        if audio is not None:
            # Graceful natural completion on normal EOF (not interrupted),
            # so valid remaining audio is not cut off at video EOF.
            if normal_eof and not interrupted and timeline is not None:
                if audio.is_running():
                    timeout = audio_completion_timeout(
                        audio.launched_at if audio.launched_at is not None
                        else clock.current_time(),
                        clock.current_time(),
                        media_duration,
                    )
                    audio.wait_for_exit(timeout=timeout)
                    timeline.audio_waited_for_exit = True
            if timeline is not None:
                timeline.audio_exit_at = audio.exit_at
            # Final guarantee: never leave FFplay running.
            audio.stop()
        terminal.restore()

    if config.debug:
        _report_frames(selector)
        _report_smoothing(smoother)
        _report_stats(clock)
        _report_sync(timeline)
    if interrupted:
        print("\nInterrupted by user. Exiting cleanly.", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = config_from_args(args)

    reader = None
    terminal = None
    audio = None
    timeline = None
    try:
        renderer = RGBAsciiRenderer(config)
        clock = FrameClock(config.fps)
        terminal = TerminalRenderer(config)
        terminal.init()

        # Optional media probes: duration (for the audio-completion timeout) and
        # source dimensions (for aspect-preserving sizing). Both degrade
        # gracefully to defaults when FFprobe is unavailable.
        media_duration = probe_media_duration(args.video)
        src_size = probe_video_size(args.video)
        video_aspect = (src_size[0] / src_size[1]) if src_size else None

        width, height = terminal.output_size(video_aspect)
        if config.debug:
            print(f"Terminal:         {terminal.width} x {terminal.height}", file=sys.stderr)
            print(f"Source:           "
                  f"{(src_size[0], src_size[1]) if src_size else 'unknown'} "
                  f"({(f'{video_aspect:.3f}') if video_aspect else '16:9 default'})",
                  file=sys.stderr)
            print(f"ASCII resolution: {width} x {height}", file=sys.stderr)
            print(f"Preset:           {config.preset or '(default/custom)'}", file=sys.stderr)
            print(f"Gradient:         {len(config.chars)} chars", file=sys.stderr)
            print(f"Color:            {'on' if config.enable_color else 'off'}", file=sys.stderr)
            print(f"Target FPS:       {config.fps}", file=sys.stderr)

        # Single master playback reference shared by the video and audio
        # timelines on the same monotonic clock.
        playback_start = clock.current_time()

        audio_status = AudioStatus.ABSENT
        if config.enable_audio:
            audio = AudioPlayer()
            if audio.ffplay is None:
                print(
                    "FFplay not found; audio is disabled and this video will play "
                    "silently with video only.",
                    file=sys.stderr,
                )
                print(
                    "  To enable audio, install FFmpeg/FFplay "
                    "(https://ffmpeg.org/download.html) and add the folder with "
                    "ffplay.exe to your PATH, then open a NEW terminal window.",
                    file=sys.stderr,
                )
            else:
                audio_status = detect_audio_status(args.video)
                if audio_status in (AudioStatus.CONFIRMED, AudioStatus.UNKNOWN):
                    audio.start(args.video)
                    if config.debug:
                        print("FFplay audio started.", file=sys.stderr)
                else:
                    print(
                        "No audio stream detected; skipping audio.",
                        file=sys.stderr,
                    )

        timeline = PlaybackTimeline(
            playback_start=playback_start,
            video_launched_at=None,
            audio_status=audio_status,
        )

        reader = FFmpegFrameReader(args.video, width, height, fps=config.fps)
        reader.open()
        timeline.video_launched_at = reader.launched_at
        if audio is not None:
            timeline.audio_launched_at = audio.launched_at

        return run(
            reader, renderer, terminal, clock, config,
            audio, timeline, media_duration=media_duration,
            video_aspect=video_aspect,
        )
    except (FFmpegNotFoundError, FileNotFoundError, FFplayNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if reader is not None:
            reader.close()
        if audio is not None:
            audio.stop()
        if terminal is not None:
            terminal.restore()


if __name__ == "__main__":
    raise SystemExit(main())
