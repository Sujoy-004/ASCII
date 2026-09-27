"""Tests for Milestone 6: frame selection / real-time lag recovery.

Deterministic only: fake clocks, fake readers, and injected processing time
are used (no real-time timing, no real subprocesses). Exercises the
FrameSelector decision model, the drop/catch-up behavior, deadline
invariance, startup policy, and integration through `run()` (including the
M5 audio completion policy remaining intact during frame dropping).
"""

from unittest import mock

import pytest

from src.audio import AudioPlayer
from src.config import Config
from src.framesel import DropStats, FrameSelector
from src.main import run
from src.renderer import RGBAsciiRenderer
from src.sync import AudioStatus, PlaybackTimeline
from src.timing import FrameClock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeTime:
    """Deterministic fake monotonic clock exposing its current value."""

    def __init__(self, start=100.0):
        self.t = start

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class FakeReader:
    def __init__(self, frames, width=4, height=4):
        self._frames = list(frames)
        self.width = width
        self.height = height
        self.closed = False

    def read_frame(self):
        if not self._frames:
            return None
        return self._frames.pop(0)

    def close(self):
        self.closed = True


class BoomReader(FakeReader):
    def read_frame(self):
        raise KeyboardInterrupt


class SlowRenderer:
    """Renderer whose render_frame advances fake time (slow processing)."""

    def __init__(self, cost, ft):
        self.cost = cost
        self.ft = ft
        self.rendered = 0

    def render_frame(self, frame, width, height):
        self.ft.t += self.cost
        self.rendered += 1
        return "frame"


class FakeTerminal:
    def __init__(self):
        self.written = 0
        self.restored = False

    def write_frame(self, _f):
        self.written += 1

    def restore(self):
        self.restored = True


class FakeProc:
    def __init__(self, now, exits_at=None):
        self._now = now
        self._exits_at = exits_at
        self.terminated = 0

    def poll(self):
        if self._exits_at is not None and self._now() >= self._exits_at:
            return 0
        return None

    def terminate(self):
        self.terminated += 1

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 0


def _black(width=4, height=4):
    return bytes(width * height * 3)


def _frames(n):
    return [_black() for _ in range(n)]


def _clock(ft, fps=30):
    return FrameClock(fps, now=ft.now, sleep_fn=ft.sleep)


# ---------------------------------------------------------------------------
# A/B/C. On time / slightly late / clearly stale
# ---------------------------------------------------------------------------

def test_on_time_frame_is_rendered():
    """Healthy: frames whose slots have not passed are all rendered."""
    ft = FakeTime(start=10.0)
    reader = FakeReader([_black(), _black(), _black()])
    clock = _clock(ft)
    clock.start(start_time=10.0)
    sel = FrameSelector(reader, clock)

    frame, idx = sel.next()   # frame 0 (first, forced)
    assert idx == 0
    frame, idx = sel.next()   # frame 1
    assert idx == 1
    frame, idx = sel.next()   # frame 2
    assert idx == 2
    assert sel.stats.rendered == 3
    assert sel.stats.dropped == 0


def test_slightly_late_frame_is_rendered():
    """Small lateness within one display period is NOT dropped."""
    ft = FakeTime(start=10.0)
    reader = FakeReader([_black(), _black()])
    clock = _clock(ft)
    clock.start(start_time=10.0)
    sel = FrameSelector(reader, clock)

    assert sel.next()[0] is not None      # frame 0 forced render

    # Now 10ms late relative to frame 0 (deadline(1) = 10.0333, still useful:
    # its own slot has not fully passed -> deadline(2) = 10.0667).
    ft.t = 10.010
    frame, idx = sel.next()
    assert frame is not None
    assert idx == 1
    assert sel.stats.dropped == 0


def test_clearly_stale_frame_is_dropped():
    """A frame whose slot has fully passed (>= one display period) is dropped."""
    ft = FakeTime(start=10.0)
    reader = FakeReader([_black(), _black(), _black()])
    clock = _clock(ft)
    clock.start(start_time=10.0)
    sel = FrameSelector(reader, clock)

    assert sel.next()[0] is not None   # frame 0 forced

    # Jump 150ms ahead: frame 1's slot (deadline 10.0333..10.0667) has passed.
    ft.t = 10.150
    frame, idx = sel.next()
    # frames 1 and 2 are stale (their slots fully passed) -> dropped; then EOF.
    assert frame is None
    assert sel.stats.decoded == 3
    assert sel.stats.rendered == 1
    assert sel.stats.dropped == 2


# ---------------------------------------------------------------------------
# D. Multiple stale frames -> drop until useful
# ---------------------------------------------------------------------------

def test_drops_stale_frames_until_a_useful_frame_is_reached():
    ft = FakeTime(start=0.0)
    reader = FakeReader(_frames(8))
    clock = _clock(ft)
    clock.start(start_time=0.0)
    sel = FrameSelector(reader, clock)

    assert sel.next()[0] is not None       # frame 0 forced
    ft.t = 0.300                           # far behind timeline
    frame, idx = sel.next()
    # find the first frame whose slot hasn't fully passed:
    #   want now < deadline(idx+1)  => 0.300 < (idx+1)/30  => idx+1 > 9 => idx >= 10
    # but only 7 frames remain -> reader exhausts -> EOF first
    assert frame is None                   # ran out of frames while catching up
    assert sel.stats.dropped == 7          # frames 1..7 all stale, dropped


# ---------------------------------------------------------------------------
# E. Absolute deadlines unchanged after dropping
# ---------------------------------------------------------------------------

def test_dropping_does_not_shift_later_deadlines():
    ft = FakeTime(start=10.0)
    reader = FakeReader(_frames(6))
    clock = _clock(ft)
    clock.start(start_time=10.0)
    sel = FrameSelector(reader, clock)

    deadline_before = clock.deadline(5)
    assert sel.next()[0] is not None       # frame 0
    ft.t = 10.200                          # drop several frames
    frame, idx = sel.next()
    assert idx >= 2                        # something was dropped/advanced
    assert clock.deadline(5) == deadline_before   # timeline untouched


# Without an audio clock, staleness is judged against deadline(idx + 1), so it
# must honour the source timeline: frame 1 is 0.5s away even though a 1/30 slot
# has long since passed. Dropping it here would discard a frame still wanted.
def test_staleness_follows_source_timestamps_without_audio():
    ft = FakeTime(start=10.0)
    reader = FakeReader(_frames(3))
    clock = _clock(ft)
    clock.start(start_time=10.0)
    clock.set_media_timestamps((0.0, 0.500, 0.533))
    sel = FrameSelector(reader, clock)

    assert sel.next()[1] == 0              # first frame is always presented
    ft.t = 10.100                          # past 1/30, short of the 0.5s PTS
    frame, idx = sel.next()
    assert frame is not None                # frame 1 was wanted, and presented
    assert idx == 1
    assert sel.stats.dropped == 0


# ---------------------------------------------------------------------------
# F. Counters
# ---------------------------------------------------------------------------

def test_counters_decoded_rendered_dropped():
    ft = FakeTime(start=10.0)
    reader = FakeReader(_frames(5))
    clock = _clock(ft)
    clock.start(start_time=10.0)
    sel = FrameSelector(reader, clock)

    assert sel.next()[0] is not None          # frame 0 forced
    ft.t = 10.300
    assert sel.next()[0] is None              # then EOF (rest stale)
    s = sel.stats
    assert s.decoded == 5
    assert s.rendered == 1
    assert s.dropped == 4
    assert s.dropped == s.decoded - s.rendered
    assert s.drop_rate == pytest.approx(80.0)
    assert s.caught_up_events == 1
    assert s.max_burst_dropped == 4


# ---------------------------------------------------------------------------
# G. No infinite loop while catching up
# ---------------------------------------------------------------------------

def test_severe_backlog_does_not_hang_and_ends_at_eof():
    ft = FakeTime(start=0.0)
    reader = FakeReader(_frames(50))
    clock = _clock(ft)
    clock.start(start_time=0.0)
    sel = FrameSelector(reader, clock)

    assert sel.next()[0] is not None          # frame 0
    ft.t = 100.0                              # impossibly behind
    # next() must return (EOF) rather than loop forever
    frame, idx = sel.next()
    assert frame is None
    assert sel.stats.dropped == 49            # all remaining frames dropped


# ---------------------------------------------------------------------------
# H. Buffer stays bounded (no unbounded queue)
# ---------------------------------------------------------------------------

def test_selector_holds_no_frame_queue():
    """FrameSelector must not buffer frames between next() calls.

    Dropping is consuming one frame at a time and discarding it; nothing is
    retained for later (so latency cannot grow without bound).
    """
    ft = FakeTime(start=10.0)
    reader = FakeReader(_frames(20))
    clock = _clock(ft)
    clock.start(start_time=10.0)
    sel = FrameSelector(reader, clock)
    # The selector has no collection attributes that could grow.
    assert not hasattr(sel, "queue") and not hasattr(sel, "buffer")
    # Stale backlog is drained eagerly, one frame per loop iteration.
    ft.t = 100.0
    frame, _ = sel.next()            # frame 0 forced render
    assert frame is not None
    frame, _ = sel.next()            # eagerly drains stale frames -> EOF quickly
    assert frame is None
    assert sel.stats.dropped == 19


# ---------------------------------------------------------------------------
# I. EOF after dropped frames
# ---------------------------------------------------------------------------

def test_eof_after_dropping_returns_none():
    ft = FakeTime(start=10.0)
    reader = FakeReader(_frames(3))
    clock = _clock(ft)
    clock.start(start_time=10.0)
    sel = FrameSelector(reader, clock)
    assert sel.next()[0] is not None
    ft.t = 10.500
    frame, idx = sel.next()          # frames 1,2 stale -> EOF
    assert frame is None
    assert sel.stats.rendered == 1
    assert sel.stats.dropped == 2


# ---------------------------------------------------------------------------
# J. Interrupt propagates (cleanup handled by run's finally)
# ---------------------------------------------------------------------------

def test_interrupt_propagates_through_selector():
    ft = FakeTime(start=10.0)
    sel = FrameSelector(BoomReader([]), _clock(ft))
    with pytest.raises(KeyboardInterrupt):
        sel.next()


# ---------------------------------------------------------------------------
# Startup policy (section 15): first frame always rendered
# ---------------------------------------------------------------------------

def test_first_frame_rendered_despite_startup_skew():
    """Process-launch skew must not cause an empty initial catch-up burst."""
    ft = FakeTime(start=10.0)
    reader = FakeReader(_frames(4))
    clock = _clock(ft)
    clock.start(start_time=10.0)
    sel = FrameSelector(reader, clock)
    ft.t = 10.0 + 5.0                # huge startup skew before first next()
    frame, idx = sel.next()
    assert frame is not None
    assert idx == 0                  # first frame still rendered
    assert sel.stats.rendered == 1
    assert sel.stats.dropped == 0


# ---------------------------------------------------------------------------
# DropStats unit
# ---------------------------------------------------------------------------

def test_dropstats_burst_and_rate():
    s = DropStats()
    s.decoded = 10
    s.rendered = 6
    s.record_drop()
    s.record_drop()
    s.end_burst()
    s.record_drop()
    s.end_burst()
    r = s.report()
    assert r["dropped"] == 4
    assert r["drop_rate"] == pytest.approx(40.0)
    assert s.caught_up_events == 2
    assert s.max_burst_dropped == 2


# ---------------------------------------------------------------------------
# Integration through run(): healthy (section 19)
# ---------------------------------------------------------------------------

def test_healthy_run_renders_all_frames_without_dropping():
    """Fast pipeline: rendered ~= decoded, no unnecessary drops."""
    ft = FakeTime(start=0.0)
    n = 10
    reader = FakeReader(_frames(n))
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=30)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    timeline = PlaybackTimeline(playback_start=0.0, audio_status=AudioStatus.ABSENT)
    result = run(reader, RGBAsciiRenderer(config), terminal, clock, config,
                 None, timeline)
    assert result == 0
    assert terminal.written == n          # nothing dropped on a healthy system
    assert terminal.restored


# ---------------------------------------------------------------------------
# Integration through run(): simulated slow renderer (section 18/20/21)
# ---------------------------------------------------------------------------

def test_slow_renderer_drops_frames_and_recovers_but_does_not_deadlock():
    """Overloaded workload: stale frames are dropped, playback stays on the
    timeline, no deadlock, and not everything is dropped."""
    ft = FakeTime(start=0.0)
    n = 12
    reader = FakeReader(_frames(n))
    renderer = SlowRenderer(cost=0.050, ft=ft)   # 50ms > 33ms budget
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=30)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    timeline = PlaybackTimeline(playback_start=0.0, audio_status=AudioStatus.ABSENT)
    result = run(reader, renderer, terminal, clock, config, None, timeline)
    assert result == 0
    assert 0 < terminal.written < n          # dropped some, but not all
    assert renderer.rendered == terminal.written
    assert terminal.restored


def test_slow_renderer_with_audio_keeps_m5_completion_policy():
    """Frame dropping must not manipulate audio; M5 natural-exit waits intact."""
    ft = FakeTime(start=0.0)
    proc = FakeProc(now=ft.now, exits_at=6.0)   # audio runs past video EOF
    with mock.patch("src.audio.subprocess.Popen", return_value=proc):
        player = AudioPlayer(ffplay="ffplay", now=ft.now, sleep_fn=ft.sleep)
        player.start("movie.mp4")
    player.launched_at = 0.0

    n = 12
    reader = FakeReader(_frames(n))
    renderer = SlowRenderer(cost=0.050, ft=ft)
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=30)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    timeline = PlaybackTimeline(
        playback_start=0.0, audio_status=AudioStatus.CONFIRMED,
        audio_launched_at=0.0,
    )
    result = run(reader, renderer, terminal, clock, config, player, timeline,
                 media_duration=5.0)
    assert result == 0
    assert 0 < terminal.written < n           # some frames dropped
    assert proc.terminated == 0               # audio not force-killed by dropping
    assert timeline.audio_waited_for_exit is True  # M5 completion intact


def test_slow_renderer_interrupt_cleans_up():
    """Ctrl+C during an overloaded playback still cleans up audio/terminal."""
    ft = FakeTime(start=0.0)
    proc = FakeProc(now=ft.now, exits_at=None)  # never exits naturally
    with mock.patch("src.audio.subprocess.Popen", return_value=proc):
        player = AudioPlayer(ffplay="ffplay", now=ft.now, sleep_fn=ft.sleep)
        player.start("movie.mp4")
    player.launched_at = 0.0

    reader = BoomReader(_frames(10))
    renderer = SlowRenderer(cost=0.050, ft=ft)
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=30)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    timeline = PlaybackTimeline(
        playback_start=0.0, audio_status=AudioStatus.CONFIRMED,
        audio_launched_at=0.0,
    )
    result = run(reader, renderer, terminal, clock, config, player, timeline,
                 media_duration=5.0)
    assert result == 0
    assert proc.terminated == 1               # interrupt -> immediate audio stop
    assert timeline.audio_waited_for_exit is False
    assert terminal.restored



def test_frame_selector_uses_audio_media_clock_for_staleness():
    from src.framesel import FrameSelector
    from src.timing import FrameClock

    class Reader:
        width = height = 1
        def __init__(self):
            self.frames = [b"a", b"b", b"c"]
        def read_frame(self):
            return self.frames.pop(0) if self.frames else None

    media = [1.0]
    clock = FrameClock(10)
    clock.start(0.0)
    clock.set_media_clock(lambda: media[0])
    selector = FrameSelector(Reader(), clock)

    frame, idx = selector.next()  # first frame is always presented
    assert (frame, idx) == (b"a", 0)
    frame, idx = selector.next()  # frame 1 target=0.1 is stale at audio t=1.0
    assert frame is None
    assert selector.stats.dropped == 2
