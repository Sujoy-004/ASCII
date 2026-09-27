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

from src.adaptive import QualityController, apply_level
from src.audio import (
    AudioPlayer,
    FFplayNotFoundError,
    FFplayPlaybackError,
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
    probe_video_timestamps,
)
from src.terminal import TerminalRenderer
from src.timing import FrameClock
from src.video import FFmpegDecodeError, FFmpegFrameReader, FFmpegNotFoundError


def _program_name() -> str:
    """Return the name to show in usage/help for how we were invoked.

    argparse would otherwise derive it from ``sys.argv[0]``, which under
    ``python -m src.main`` is the full path to main.py and would print a bare
    ``main.py``. The installed console script keeps its own name.
    """
    stem = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    return stem if stem == "rgb-ascii" else "python -m src.main"


_ENV_EPILOG = """\
environment variables (all optional; an explicit flag always wins):
  RGB_ASCII_NO_ADAPTIVE   1 to disable adaptive quality (--no-adaptive)
  RGB_ASCII_HALF_BLOCK    1 for upper-half-block cells with two stacked colors
  RGB_ASCII_NO_COLOR      1 for monochrome glyphs only
  RGB_ASCII_NO_AUDIO      1 to skip the audio track
  RGB_ASCII_SMOOTHING     blend factor, 0.0-1.0 (0 disables)
  RGB_ASCII_FPS           fixed-FPS fallback when the source has no timestamps
  RGB_ASCII_PRESET        character ramp: default, dense, simple or blocks
  RGB_ASCII_CHARS         explicit glyph ramp, brightest character last
  RGB_ASCII_DEBUG         1 for a stderr report of timing and adaptive decisions

Booleans (the *_NO_* and *_DEBUG vars) follow one rule: any value other than
"", 0, false, no or off counts as "on". Numeric variables that cannot be read,
and out-of-range values, fall back to the default rather than being treated as
errors, so a typo degrades instead of refusing to play. The adaptive-quality
flag above is the one control worth setting per run.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=_program_name(),
        description=(
            "Play a video as real-time colored ASCII art in the terminal, "
            "with the source audio playing alongside."
        ),
        epilog=_ENV_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "video",
        help="Path to the video file to play (anywhere on the machine; "
             "relative, absolute, or with spaces).",
    )
    parser.add_argument(
        "--adaptive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Adaptively shed optional render work when a frame overruns its "
            "display slot for a sustained window: first temporal smoothing, "
            "then color. On by default. Use --no-adaptive for "
            "byte-reproducible output regardless of machine speed. Adaptive "
            "quality never alters playback timing, frame selection, or A/V "
            "synchronization, and never disables color in half-block mode, "
            "where the glyph itself carries both colors."
        ),
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
    """Build a Config from the CLI options and the ``RGB_ASCII_*`` env vars.

    The public command is simply ``python -m src.main VIDEO`` -- everything
    else is auto-detected at runtime. Precedence is: an explicit CLI flag,
    then the environment, then the ``Config`` default.

    Environment values are deliberately *lenient*. These are development and
    test knobs rather than a user-facing configuration surface, so a
    malformed, out-of-range, or unrecognised value falls back to the default
    instead of aborting playback; a strict dataclass still guards direct
    construction (see ``Config``). ``RGB_ASCII_FPS=0`` and
    ``RGB_ASCII_SMOOTHING=5`` are ignored/clamped rather than rejected, and
    ``RGB_ASCII_SMOOTHING=5`` is additionally clamped by the smoother itself.

    The one thing leniency cannot cover is a *combination* of individually
    valid values that cannot be rendered at all. That is reported as an error
    here, at the parsing boundary, so it can never reach the render loop as a
    traceback.

    Raises:
        ValueError: if the selected combination cannot be rendered.
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
    if _env_bool("RGB_ASCII_HALF_BLOCK"):
        config.blocks = True
    if _env_bool("RGB_ASCII_NO_ADAPTIVE"):
        config.adaptive_quality = False

    # An explicit flag beats the environment, so a script can force either
    # value regardless of an inherited RGB_ASCII_NO_ADAPTIVE.
    if args.adaptive is not None:
        config.adaptive_quality = args.adaptive

    # Half-block output carries both pixel colors in the glyph itself
    # (foreground + background), so color is not optional there. Rendering it
    # without color is not a degraded mode, it is undefined -- reject it while
    # parsing rather than raising from inside the render loop on frame 0.
    if config.blocks and not config.enable_color:
        raise ValueError(
            "half-block rendering encodes both pixel colors in the glyph "
            "character, so it cannot be combined with no-color; unset one of "
            "RGB_ASCII_HALF_BLOCK or RGB_ASCII_NO_COLOR"
        )

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
    print("  Representation:   RGB (luminance/ASCII derived)", file=sys.stderr)
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


def _report_sync(timeline: PlaybackTimeline | None, clock: FrameClock) -> None:
    """Print A/V synchronization diagnostics (only used in debug mode)."""
    if timeline is None:
        return
    t = timeline
    print("Sync:", file=sys.stderr)
    print(
        f"  Audio startup offset: {_fmt(t.audio_startup_offset)} (from playback start)",
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
    print(
        f"  Sync clock:           {clock.clock_source}",
        file=sys.stderr,
    )
    print(
        f"  Max |A/V drift|:      {_fmt(t.max_av_drift)}",
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
    first_frame: bytes | None = None,
) -> int:
    """Run the continuous playback loop, cleaning up on EOF and Ctrl+C.

    Returns 0, or raises FFplayPlaybackError if the audio process failed. Owns
    the try/finally cleanup so terminal state, the FFmpeg process, and the FFplay
    audio process are always restored regardless of how playback ends.

    Each frame is scheduled against an absolute timeline deadline provided by
    the FrameClock; processing time is recorded separately from presentation.

    Startup synchronization:
      - The decoder's first frame is obtained *before* the playback origin
        exists (``first_frame`` when the caller already read it, otherwise read
        it here), so FFmpeg's spawn/filter/decode latency is not charged to the
        playback clock.
      - The origin is then the earliest instant at which a frame could actually
        be presented, which makes ``deadline(0)`` the origin itself: frame 0 is
        presented immediately and every later deadline is in the future.
      - The media clock is adopted once, here, and only if it is already
        readable. A clock that arrives late is never adopted, so FFplay's own
        startup latency can never be reclassified as playback lateness.

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
    audio_failure: int | None = None
    selector = FrameSelector(reader, clock, first_frame)
    smoother = TemporalSmoother(config)
    blocks = config.blocks
    # Display rows: in half-block mode each cell shows two decoded rows, so the
    # visible grid is half the decoded height; rendering re-scales the decode
    # resolution to the terminal grid before pairing rows into ▀ cells.
    render_rows = (reader.height // 2) if blocks else reader.height
    current_width, current_height = reader.width, render_rows

    # Adaptive quality watches measured per-frame work and, only after a full
    # window of sustained evidence, sheds the most expensive optional work
    # first. Its levers are discovered, not assumed: only work that is
    # actually enabled and actually optional is offered. Half-block output
    # carries color in the glyph itself, so color is not optional there and is
    # never offered -- which is what keeps it from being switched off. It never
    # alters the clock, deadlines, or frame selection.
    quality: QualityController | None = None
    levers: list[tuple[object, str]] = []
    if smoother.enabled:
        levers.append((smoother, "enabled"))
    if config.enable_color and not blocks:
        levers.append((config, "enable_color"))
    if config.adaptive_quality and levers:
        quality = QualityController(max_level=len(levers))
    applied_level = 0
    try:
        # Startup synchronization: block for the first frame *before* any
        # playback timeline exists, so FFmpeg's spawn/filter/decode latency is
        # not charged to the clock as playback lateness. Interrupting during
        # this read is an ordinary Ctrl+C, so it is handled like any other.
        selector.prime()
        clock.start()
        clock.set_media_timestamps(getattr(reader, "media_timestamps", None))
        if audio is not None:
            clock.set_media_clock(audio.media_position)
        if clock.adopt_media_clock() and config.debug:
            print(
                f"FFplay audio clock ready at {clock.media_time():.3f}s; "
                "using it as the presentation clock.",
                file=sys.stderr,
            )
        if timeline is not None:
            # The origin is a measured fact, not a prediction made before the
            # processes were launched.
            timeline.playback_start = clock.start_time
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

            # Adaptive quality measures the work this player is responsible
            # for -- smooth, resize, render, write -- but not decode (already
            # done) and not the wait. Sampled before smoothing, which
            # TimingStats.total_processing deliberately excludes. Only
            # *presented* frames report work, so a failure that lives purely
            # inside the FFmpeg pipe is invisible here by design; that is a
            # scheduling symptom, not a rendering-cost one.
            work_start = clock.current_time() if quality else 0.0
            frame = smoother.smooth(frame)  # M7 visual smoothing (pass-through when off)
            proc_start = clock.current_time()
            if blocks:
                if (current_width, current_height) == (reader.width, render_rows):
                    ascii_frame = renderer.render_frame_blocks(
                        frame, reader.width, render_rows
                    )
                else:
                    ascii_frame = renderer.render_resized_blocks_frame(
                        frame,
                        reader.width,
                        reader.height,
                        current_width,
                        current_height,
                    )
            elif (current_width, current_height) == (reader.width, reader.height):
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
            if quality is not None:
                # Budget this frame against the display slot it was actually
                # scheduled into -- the gap to the *next* frame's canonical
                # presentation time -- not against 1/fps. A variable-rate
                # source legitimately gives some frames a slot several times
                # the nominal frame duration; charging 1/fps there would
                # report a busy machine for a frame that finished in a quarter
                # of its slot and shed quality that was never needed. A
                # duplicate source PTS creates no display interval, so it
                # yields a zero (or non-positive) gap and falls back to the
                # nominal duration rather than dividing by zero.
                slot = (
                    clock.target_media_time(src_index + 1)
                    - clock.target_media_time(src_index)
                )
                if not slot > 0.0:
                    slot = clock.frame_duration
                level = quality.record(clock.current_time() - work_start, slot)
                if level != applied_level:
                    applied_level = level
                    apply_level(level, levers)
            clock.wait_until(clock.deadline(src_index), proc_start)
            if timeline is not None:
                media_now = clock.media_time()
                target_media = clock.target_media_time(src_index)
                if media_now is not None:
                    timeline.last_av_drift = media_now - target_media
                    timeline.max_av_drift = max(
                        timeline.max_av_drift, abs(timeline.last_av_drift)
                    )
                if selector.stats.rendered == 1:
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
            #
            # This runs inside `finally`, so a second Ctrl+C here would skip
            # `audio.stop()` and `terminal.restore()` below and orphan FFplay
            # with the cursor still hidden. A user who interrupts again has
            # already said they want out now, so honour that and fall through
            # to the same cleanup the first interrupt would have reached.
            try:
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
            except KeyboardInterrupt:
                interrupted = True
            if normal_eof and not interrupted and not audio.is_running():
                # FFplay is already gone by video EOF. A non-zero status means
                # the audio process failed, which must not be reported as a
                # clean run. Read before stop() so our own termination is never
                # mistaken for a failure, and after the graceful wait so a
                # process still running at the timeout is not flagged.
                audio_failure = audio.exit_code or None
            if timeline is not None:
                timeline.audio_exit_at = audio.exit_at
            # Final guarantee: never leave FFplay running.
            audio.stop()
        terminal.restore()

    if config.debug:
        _report_frames(selector)
        _report_smoothing(smoother)
        if quality is not None:
            # Name what was actually shed rather than a fixed ladder: the
            # levers are discovered, so a level's meaning depends on which
            # optional work this run actually had.
            shed = [attr for i, (_t, attr) in enumerate(levers) if quality.level > i]
            print(f"  Quality level:   {quality.level} of {len(levers)}"
                  f" (worst needed: {quality.worst_level})",
                  file=sys.stderr)
            print(f"  Quality shed:    {', '.join(shed) if shed else 'nothing'}",
                  file=sys.stderr)
        _report_stats(clock)
        _report_sync(timeline, clock)
    if interrupted:
        print("\nInterrupted by user. Exiting cleanly.", file=sys.stderr)
    if audio_failure is not None:
        raise FFplayPlaybackError(
            f"FFplay exited with status {audio_failure} before the video "
            "finished; audio playback did not complete."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = config_from_args(args)
    except ValueError as exc:
        # A configuration the renderer cannot honour. Reported as a usage
        # error (exit 2, like argparse) so a script can tell "you asked for
        # something impossible" apart from "playback failed" (exit 1).
        print(f"Error: {exc}", file=sys.stderr)
        return 2

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
        video_timestamps = probe_video_timestamps(
            args.video, duration=media_duration
        )

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
            print(
                f"Frame timestamps:  {'source PTS' if video_timestamps else 'fixed FPS fallback'}",
                file=sys.stderr,
            )

        # Audio *detection* is cheap metadata and happens with the other probes.
        # The FFplay process itself is started later, once the decoder is warm,
        # so its media clock is already readable at the playback origin.
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
                if audio_status is AudioStatus.ABSENT:
                    print(
                        "No audio stream detected; skipping audio.",
                        file=sys.stderr,
                    )

        # playback_start is a placeholder: run() replaces it with the real
        # origin once the decoder is warm and the clock basis is settled.
        timeline = PlaybackTimeline(
            playback_start=0.0,
            video_launched_at=None,
            audio_status=audio_status,
        )

        reader = FFmpegFrameReader(
            args.video, width, height * 2 if config.blocks else height,
            fps=config.fps,
        )
        reader.media_timestamps = video_timestamps
        reader.open()
        timeline.video_launched_at = reader.launched_at

        # Prime the decoder: block for the first frame *before* any playback
        # timeline exists, so FFmpeg's spawn/filter/decode latency is not billed
        # to the clock as playback lateness.
        first_frame = reader.read_frame()

        if (
            audio is not None
            and audio.ffplay
            and audio_status in (AudioStatus.CONFIRMED, AudioStatus.UNKNOWN)
        ):
            audio.start(args.video)
            if config.debug:
                print("FFplay audio started.", file=sys.stderr)
            # Wait for FFplay's status line now that the first frame is already
            # buffered, so a ready clock is adopted at the playback origin
            # instead of arriving late and being mistaken for a fast-forward.
            if not audio.wait_for_media_clock() and config.debug:
                print(
                    "FFplay audio clock not ready in time; pacing on the "
                    "monotonic clock.",
                    file=sys.stderr,
                )
        if audio is not None:
            timeline.audio_launched_at = audio.launched_at

        return run(
            reader, renderer, terminal, clock, config,
            audio, timeline, media_duration=media_duration,
            video_aspect=video_aspect, first_frame=first_frame,
        )
    except (
        FFmpegNotFoundError,
        FFmpegDecodeError,
        FileNotFoundError,
        FFplayNotFoundError,
        FFplayPlaybackError,
        # Backstop. Anything that reaches here is a configuration or input
        # problem the user can act on, so it is reported as a message rather
        # than a traceback. The renderer's own half-block/colour guard raises
        # this; config_from_args rejects that combination up front, so this
        # only fires for a path added later.
        ValueError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, ValueError) else 1
    finally:
        if reader is not None:
            reader.close()
        if audio is not None:
            audio.stop()
        if terminal is not None:
            terminal.restore()


if __name__ == "__main__":
    raise SystemExit(main())
