"""Startup synchronization and clock-state transitions.

Two invariants are pinned here.

Startup: decoder startup latency must not be charged to the playback clock.
Before the first frame is in hand there is no valid basis for presenting
anything, so the playback origin is established at that moment -- not before the
processes were launched. The symptom of getting this wrong is a burst of frames
dropped as "stale" that were never actually late, growing linearly with how long
FFmpeg took to warm up.

Clock state: the authoritative clock source is explicit, and every change of
source preserves media time, so switching can never introduce a scheduling step.
"""

import io

import pytest

from src.audio import AudioPlayer, FFplayPlaybackError
from src.config import Config
from src.framesel import FrameSelector
from src.main import run
from src.renderer import RGBAsciiRenderer
from src.sync import PlaybackTimeline
from src.timing import (
    FALLBACK_AFTER_AUDIO_FAILURE,
    FFPLAY_AUDIO,
    MONOTONIC,
    FrameClock,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeTime:
    """Deterministic monotonic clock; sleeping advances it."""

    def __init__(self, start=1000.0):
        self.t = start
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


class WarmupReader:
    """Reader whose first read blocks, modelling decoder startup latency.

    Every other fake reader returns instantly, which is why startup latency was
    previously invisible to the suite: the clock simply never moved while the
    decoder warmed up.
    """

    def __init__(self, ft, frames=None, delay=0.0, timestamps=None):
        self.ft = ft
        self._frames = list(frames) if frames is not None else []
        self.delay = delay
        self._warmed = False
        self.width = 4
        self.height = 4
        self.media_timestamps = timestamps
        self.closed = False
        self.reads = 0

    def read_frame(self):
        self.reads += 1
        if not self._warmed:
            self._warmed = True
            self.ft.t += self.delay  # process spawn + filter/decode warm-up
        if not self._frames:
            return None
        return self._frames.pop(0)

    def close(self):
        self.closed = True


class StubAudio:
    """Audio whose media clock reads 0 at launch and advances at 1x.

    Models the production ordering: FFplay is launched *after* the decoder is
    warm, so its clock is already readable at the playback origin and reports
    ~0 there. ``ready_at`` models a clock that only becomes readable later, which
    is FFplay's status line not having arrived yet.
    """

    def __init__(self, launched_at, now, ready_at=None):
        self.launched_at = launched_at
        self._now = now
        self._ready_at = ready_at
        self.exit_code = 0
        self.exit_at = None
        self.stopped = False

    def media_position(self):
        if self._ready_at is not None and self._now() < self._ready_at:
            return None
        return self._now() - self.launched_at

    def is_running(self):
        return True

    def wait_for_exit(self, timeout=None):
        return True

    def stop(self):
        self.stopped = True


class FakeTerminal:
    def __init__(self):
        self.written = 0
        self.restored = False

    def refresh_size(self):
        return False

    def output_size(self, _aspect):
        return (4, 4)

    def write_frame(self, _frame):
        self.written += 1

    def restore(self):
        self.restored = True


class FakeProc:
    """Popen stand-in whose exit can be scripted, optionally on a deadline."""

    def __init__(self, exited=False, exit_code=0, die_at=None, now=None,
                 die_exit_code=1):
        self._exited = exited
        self._exit_code = exit_code
        self._die_at = die_at
        self._die_exit_code = die_exit_code
        self._now = now
        self.terminated = 0
        self.killed = 0

    def poll(self):
        if not self._exited and self._die_at is not None and self._now() >= self._die_at:
            self._exited = True
            self._exit_code = self._die_exit_code
        return None if not self._exited else self._exit_code

    def terminate(self):
        self.terminated += 1
        self._exited = True
        self._exit_code = 1

    def kill(self):
        self.killed += 1
        self._exited = True
        self._exit_code = 1

    def wait(self, timeout=None):
        return self._exit_code


def _audio(ft, exited=False, exit_code=0, position=None, die_at=None):
    """A real AudioPlayer on the fake clock, with a scriptable FFplay process.

    ``position`` seeds a status line so the media clock is readable; without it
    FFplay's clock never becomes valid, which is the "not ready in time" case.
    ``die_at`` makes the process exit once fake time reaches it, which is how a
    mid-playback FFplay failure is modelled.
    """
    player = AudioPlayer(ffplay="ffplay", now=ft.now, sleep_fn=ft.sleep)
    player.launched_at = ft.t
    player._process = FakeProc(exited=exited, exit_code=exit_code,
                               die_at=die_at, now=ft.now,
                               die_exit_code=exit_code)
    if position is not None:
        player._read_stats(io.BytesIO(f"{position:8.3f} M-A:  0.000\r".encode()))
    return player


def _play(ft, reader, audio=None, fps=30, config=None, timeline=None, clock=None):
    """Run the real playback loop and return (clock, stats, terminal)."""
    config = config or Config(enable_color=False, fps=1000)
    clock = clock or FrameClock(fps, now=ft.now, sleep_fn=ft.sleep)
    box = {}
    terminal = FakeTerminal()
    real = FrameSelector

    class Capturing(real):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            box["stats"] = self.stats

    import src.main as main_module

    main_module.FrameSelector = Capturing
    try:
        run(
            reader, RGBAsciiRenderer(config), terminal, clock, config,
            audio, timeline,
        )
    finally:
        main_module.FrameSelector = real
    return clock, box["stats"], terminal


def _frames(n):
    return [bytes(4 * 4 * 3) for _ in range(n)]


# ---------------------------------------------------------------------------
# 1-2. Decoder startup latency is not playback lateness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("delay", [0.1, 0.2, 0.3, 0.5])
def test_decoder_startup_delay_produces_no_stale_burst(delay):
    """A slow decoder must not cause frames to be dropped as stale.

    Charging the warm-up to the clock makes every deadline after the origin sit
    `delay` seconds in the past, which drops `delay * fps` frames that were in
    fact perfectly timely.
    """
    ft = FakeTime()
    _, stats, _ = _play(ft, WarmupReader(ft, _frames(60), delay=delay))

    assert stats.decoded == 60
    assert stats.rendered == 60
    assert stats.dropped == 0
    assert stats.max_burst_dropped == 0


def test_playback_origin_is_the_instant_the_first_frame_arrives():
    """The origin is established when a frame becomes presentable, not before."""
    ft = FakeTime()
    reader = WarmupReader(ft, _frames(4), delay=0.3)
    timeline = PlaybackTimeline(playback_start=0.0)

    clock, _, _ = _play(ft, reader, timeline=timeline)

    # The origin is the post-warm-up instant, not the pre-launch one.
    assert clock.start_time == pytest.approx(1000.0 + 0.3)
    assert timeline.playback_start == pytest.approx(1000.0 + 0.3)


def test_first_frame_is_not_forced_late_by_process_startup():
    """deadline(0) is the origin, so frame 0 is never behind the timeline."""
    ft = FakeTime()
    clock, _, _ = _play(ft, WarmupReader(ft, _frames(5), delay=0.4))

    # target_media_time(0) is always 0 (timestamps are normalized), so the first
    # frame's deadline is the origin itself and the next is a full period later.
    assert clock.deadline(0) == pytest.approx(clock.start_time)
    assert clock.deadline(1) == pytest.approx(clock.start_time + 1 / 30)


def test_interrupting_the_decoder_warmup_is_a_clean_interrupt():
    """Ctrl+C while the decoder is still starting must not escape run()."""

    class InterruptingReader(WarmupReader):
        def read_frame(self):
            raise KeyboardInterrupt

    ft = FakeTime()
    _, stats, _ = _play(ft, InterruptingReader(ft))
    assert stats.decoded == 0


# ---------------------------------------------------------------------------
# 3-4. CFR and VFR startup
# ---------------------------------------------------------------------------


def test_cfr_startup_paces_from_the_first_frame():
    ft = FakeTime()
    clock, stats, _ = _play(ft, WarmupReader(ft, _frames(20), delay=0.25))

    assert stats.dropped == 0
    assert stats.rendered == 20
    assert clock.deadline(5) == pytest.approx(clock.start_time + 5 / 30)


def test_vfr_startup_paces_from_the_first_frame():
    """Source PTS still drive deadlines; the origin just moves later."""
    timestamps = (0.0, 0.033, 0.500, 0.533, 0.600, 0.633)
    ft = FakeTime()
    reader = WarmupReader(ft, _frames(len(timestamps)), delay=0.25,
                          timestamps=timestamps)
    clock, stats, _ = _play(ft, reader)

    # The origin moves with the warm-up, and PTS still decide the deadlines.
    assert clock.start_time == pytest.approx(1000.0 + 0.25)
    assert clock.deadline(2) == pytest.approx(clock.start_time + 0.500)
    assert clock.deadline(3) == pytest.approx(clock.start_time + 0.533)
    # Nothing is dropped: the tail of a VFR timeline whose final PTS runs past
    # the fixed-FPS grid still gets a real display slot.
    assert stats.dropped == 0
    assert stats.rendered == len(timestamps)


def test_vfr_final_frame_is_not_dropped(timestamps=(0.0, 0.033, 0.500, 0.533)):
    """The final frame keeps a real display slot past the PTS list."""
    ft = FakeTime()
    reader = WarmupReader(ft, _frames(len(timestamps)), timestamps=timestamps)
    _, stats, _ = _play(ft, reader)
    assert stats.dropped == 0
    assert stats.rendered == len(timestamps)


def test_vfr_timeline_tracks_the_reader_index():
    """A primed frame does not shift the source index used for deadlines."""
    timestamps = (0.0, 0.400, 0.433)
    ft = FakeTime()
    reader = WarmupReader(ft, _frames(3), delay=0.2, timestamps=timestamps)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.set_media_timestamps(timestamps)
    selector = FrameSelector(reader, clock)
    selector.prime()

    frame, index = selector.next()
    assert (frame is not None, index) == (True, 0)
    assert clock.target_media_time(index) == pytest.approx(0.0)
    assert clock.target_media_time(index + 1) == pytest.approx(0.400)


# ---------------------------------------------------------------------------
# 5. FFplay startup latency is not playback lateness either
# ---------------------------------------------------------------------------


def test_delayed_ffplay_startup_does_not_fast_forward_the_video():
    """A clock that only becomes readable after the origin is never adopted.

    Adopting it later would rebase the origin to `now - position`, dragging it
    into the past by however much audio had already played, and mark the frames
    decoded in the meantime as stale. That is FFplay's startup latency being
    reclassified as playback lateness.

    The stub is deliberately made to report a position well *ahead* of the
    video -- audio that has been playing for five seconds while the video has
    shown none. If a non-authoritative clock could reach the scheduler at all,
    this is the value that would fast-forward the video past everything.
    """
    delay = 0.2
    origin = 1000.0 + delay
    ft = FakeTime()
    audio = StubAudio(launched_at=origin - 5.0, now=ft.now, ready_at=origin + 0.2)
    reader = WarmupReader(ft, _frames(30), delay=delay)

    clock, stats, _ = _play(ft, reader, audio=audio)

    assert clock.clock_source == MONOTONIC
    assert stats.dropped == 0
    assert stats.rendered == 30
    # It became readable mid-run, claiming far more audio than the video has
    # shown -- and it changed nothing.
    assert audio.media_position() > 5.0
    assert clock.media_time() is None


# ---------------------------------------------------------------------------
# 7-8. Clock state transitions
# ---------------------------------------------------------------------------


def test_without_audio_the_monotonic_clock_is_authoritative():
    ft = FakeTime()
    clock, _, _ = _play(ft, WarmupReader(ft, _frames(4)))

    assert clock.clock_source == MONOTONIC
    assert clock.media_time() is None


def test_a_ready_audio_clock_is_adopted_at_the_origin():
    delay = 0.2
    ft = FakeTime()
    # FFplay is launched after the decoder is warm, so it reads 0 at the origin.
    audio = StubAudio(launched_at=1000.0 + delay, now=ft.now)
    clock, stats, _ = _play(ft, WarmupReader(ft, _frames(30), delay=delay),
                         audio=audio)

    assert clock.clock_source == FFPLAY_AUDIO
    assert stats.dropped == 0
    assert clock.deadline(0) == pytest.approx(clock.start_time)


def test_reading_the_clock_never_adopts_it():
    """A non-authoritative clock is invisible to the scheduler.

    Not just unadopted -- unreadable-by-decision. Otherwise a stray value from
    FFplay could still steer frame selection while the debug output insisted the
    monotonic clock was in charge.
    """
    ft = FakeTime()
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start(1000.0)
    clock.set_media_clock(lambda: 1.5)

    assert clock.media_time() is None
    assert clock.clock_source == MONOTONIC


def test_adoption_anchors_the_origin_to_the_reported_media_position():
    """Adopting a clock at position P makes media time read exactly P."""
    ft = FakeTime()
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start(1000.0)
    clock.set_media_clock(lambda: 0.250)

    assert clock.adopt_media_clock() is True
    assert clock.clock_source == FFPLAY_AUDIO
    # Monotonic basis and media basis now agree: 1000.0 -> 0.250 of media time.
    assert clock.media_time() == pytest.approx(0.250)
    assert ft.now() - clock.start_time == pytest.approx(0.250)


def test_adoption_declines_a_clock_that_is_not_readable_yet():
    ft = FakeTime()
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start(1000.0)
    clock.set_media_clock(lambda: None)

    assert clock.adopt_media_clock() is False
    assert clock.clock_source == MONOTONIC
    assert clock.start_time == pytest.approx(1000.0)


# ---------------------------------------------------------------------------
# 9-10. FFplay failure abandons the stale clock
# ---------------------------------------------------------------------------


def test_ffplay_exit_abandons_the_stale_audio_clock():
    ft = FakeTime()
    audio = _audio(ft, position=0.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start(1000.0)
    clock.set_media_clock(audio.media_position)
    assert clock.adopt_media_clock() is True

    audio._process._exited = True

    assert clock.media_time() is None
    assert clock.clock_source == FALLBACK_AFTER_AUDIO_FAILURE


def test_fallback_continues_on_the_monotonic_basis():
    ft = FakeTime()
    audio = _audio(ft, position=0.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start(1000.0)
    clock.set_media_clock(audio.media_position)
    clock.adopt_media_clock()

    ft.t = 1005.0
    audio._process._exited = True
    clock.media_time()  # performs the transition

    # Deadlines keep advancing on the monotonic basis.
    assert clock.deadline(1) > clock.start_time
    assert clock.start_time < 1005.0


def test_dead_stats_reader_is_not_served_as_a_live_clock():
    """A live FFplay whose status line stopped arriving must not look healthy."""
    ft = FakeTime()
    audio = _audio(ft, position=2.0)
    assert audio.media_position() == pytest.approx(2.0)

    ft.t += 60.0  # no status line for a minute
    assert audio.media_position() is None


# ---------------------------------------------------------------------------
# 11. Continuity across a source change
# ---------------------------------------------------------------------------


def test_switching_to_the_monotonic_basis_preserves_media_time():
    """The scenario: audio reads 12.350s, FFplay dies, monotonic takes over.

    The next media time must still be ~12.350s. Rebasing the origin to the last
    value the audio clock reported is what makes that true.
    """
    ft = FakeTime()
    audio = _audio(ft, position=0.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start(1000.0)
    clock.set_media_clock(audio.media_position)
    clock.adopt_media_clock()

    ft.t = 1012.350
    audio._read_stats(io.BytesIO(b"  12.350 M-A:  0.000\r"))
    before = clock.media_time()
    assert before == pytest.approx(12.350)

    ft.t = 1012.400
    expected = audio.media_position()  # 12.400 -- still alive at this instant
    assert expected == pytest.approx(12.400)

    audio._process._exited = True
    assert clock.media_time() is None

    after = ft.now() - clock.start_time
    # The switch of source changes nothing except who is asking: media time picks
    # up exactly where the audio clock left off, rather than jumping to some
    # unrelated value derived from the monotonic basis.
    assert after == pytest.approx(expected, abs=0.001)
    assert after != pytest.approx(8.2, abs=0.5)
    assert after != pytest.approx(17.9, abs=0.5)


def test_monotonic_media_time_keeps_advancing_after_the_fallback():
    ft = FakeTime()
    audio = _audio(ft, position=0.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start(1000.0)
    clock.set_media_clock(audio.media_position)
    clock.adopt_media_clock()

    ft.t = 1004.0
    audio._process._exited = True
    clock.media_time()

    ft.t = 1005.0
    assert ft.now() - clock.start_time == pytest.approx(5.0, abs=0.05)


# ---------------------------------------------------------------------------
# 12. Debug state reflects the runtime source
# ---------------------------------------------------------------------------


def test_debug_clock_source_reports_the_actual_source(capsys):
    """A run with no audio must not claim the audio clock is authoritative."""
    from src.main import _report_sync

    ft = FakeTime()
    clock, _, _ = _play(ft, WarmupReader(ft, _frames(3)))
    assert clock.clock_source == MONOTONIC

    _report_sync(PlaybackTimeline(playback_start=clock.start_time), clock)
    assert "Sync clock:           monotonic" in capsys.readouterr().err


def test_debug_clock_source_follows_a_fallback(capsys):
    ft = FakeTime()
    audio = _audio(ft, position=0.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start(1000.0)
    clock.set_media_clock(audio.media_position)
    clock.adopt_media_clock()
    audio._process._exited = True
    clock.media_time()

    from src.main import _report_sync

    _report_sync(PlaybackTimeline(playback_start=clock.start_time), clock)
    assert "Sync clock:           fallback-after-audio-failure" in (
        capsys.readouterr().err
    )


# ---------------------------------------------------------------------------
# The handoff, end to end through run()
# ---------------------------------------------------------------------------


def test_audio_failure_mid_run_falls_back_without_losing_continuity():
    """The full FFPLAY_AUDIO -> FALLBACK transition, driven through run().

    Every other fallback observation in the suite pokes the clock directly, so
    the integration was unproven: nothing checked that a real AudioPlayer dying
    mid-playback leaves pacing intact for the rest of the run.

    FFplay reports 0.0 at the origin, so the clock is adopted there. It then
    exits cleanly at 1000.5, having last reported 0.5. A clean early exit is
    not a failure, so playback must continue -- and it continues on the
    rebased monotonic clock, which for a 1x clock means the origin does not
    move at all.
    """
    ft = FakeTime()
    audio = _audio(ft, position=0.0, die_at=1000.5, exit_code=0)
    clock, stats, _ = _play(ft, WarmupReader(ft, _frames(40), delay=0.0),
                            audio=audio, fps=30)

    assert clock.clock_source == FALLBACK_AFTER_AUDIO_FAILURE
    # Continuity: rebasing onto 0.5 s of media at 1000.5 keeps the origin put.
    assert clock.start_time == pytest.approx(1000.0)
    # No burst at the switch instant, and nothing shed overall.
    assert stats.dropped == 0
    assert stats.rendered == 40
    assert stats.max_burst_dropped == 0
    # Playback ran to its natural end. Frame n is presented at start + n/fps
    # (deadline(n) is the *end* of frame n-1's slot), so the 40th lands at 39/30.
    assert ft.t == pytest.approx(1000.0 + 39 / 30)


def test_ffplay_dying_mid_run_with_nonzero_status_is_reported():
    """A failing FFplay still fails the run, having lost the clock first.

    The fallback exists to keep pacing honest while the process is gone; it is
    not a licence to paper over an FFplay that exited with an error.
    """
    ft = FakeTime()
    audio = _audio(ft, position=0.0, die_at=1000.5, exit_code=2)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)

    with pytest.raises(FFplayPlaybackError):
        _play(ft, WarmupReader(ft, _frames(40), delay=0.0),
              audio=audio, clock=clock)

    assert clock.clock_source == FALLBACK_AFTER_AUDIO_FAILURE


def test_ffplay_dead_at_startup_is_never_adopted():
    """A process that died before the origin has no clock to give."""
    ft = FakeTime()
    audio = _audio(ft, position=0.0, exited=True, exit_code=2)
    # A status line was seen, but the process is gone: the reading is frozen.
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)

    with pytest.raises(FFplayPlaybackError):
        _play(ft, WarmupReader(ft, _frames(30), delay=0.0),
              audio=audio, clock=clock)

    # The frozen 0.0 reading was never adopted, so no audio-derived origin
    # exists to be wrong about.
    assert clock.clock_source == MONOTONIC


def test_wait_for_media_clock_returns_as_soon_as_the_status_line_lands():
    ft = FakeTime()
    audio = _audio(ft)
    audio._read_stats(io.BytesIO(b"  0.000 M-A:  0.000\r"))
    assert audio.wait_for_media_clock(timeout=10.0) is True
    assert ft.slept == []  # the event was already set


def test_wait_for_media_clock_gives_up_when_ffplay_is_already_dead():
    """A dead FFplay's clock is never coming, so waiting is pure dead time.

    This is the only test in the suite that measures real elapsed time, and it
    has to: the old implementation blocked on the event for the whole timeout,
    which no fake clock can observe. The gap is enormous (5 s of blocking versus
    a 20 ms poll), so a loose bound is not flaky.
    """
    import time

    ft = FakeTime()
    audio = _audio(ft, exited=True, exit_code=2)

    started = time.monotonic()
    assert audio.wait_for_media_clock(timeout=5.0) is False
    elapsed = time.monotonic() - started

    assert ft.slept == []
    assert elapsed < 1.0, f"blocked {elapsed:.2f}s on an already-dead FFplay"


def test_wait_for_media_clock_times_out_while_ffplay_runs_but_stays_silent():
    """A live FFplay that never reports still falls through, on a bounded wait."""
    ft = FakeTime()
    audio = _audio(ft)

    def wait():
        return audio.wait_for_media_clock(timeout=0.25)

    assert wait() is False
    assert 0.2 < sum(ft.slept) <= 0.3


def test_wait_for_media_clock_with_zero_timeout_does_not_block():
    ft = FakeTime()
    audio = _audio(ft)
    assert audio.wait_for_media_clock(timeout=0.0) is False
    assert ft.slept == []


def test_media_position_is_none_after_stop():
    """A stopped FFplay has no clock, even though it last reported one.

    ``stop()`` clears ``_process``, and the frozen last reading must not be
    served as a live position -- the docstring and the dead-process branch both
    say a stopped process yields None, and the two must agree.
    """
    ft = FakeTime()
    audio = _audio(ft, position=2.0)
    assert audio.media_position() == pytest.approx(2.0)
    audio.stop()
    assert audio.media_position() is None
