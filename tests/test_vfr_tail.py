"""The presentation boundary at the end of a source's frame list.

``FrameSelector`` judges frame ``n`` stale once the display slot of frame
``n+1`` has begun, so it asks the clock for ``target_media_time(n + 1)``. For
the final frame that index is *past* the end of the source's presentation
timestamps, and the clock has to answer.

Answering from the fixed-FPS grid is wrong twice over: it switches timing models
halfway through a timeline that was trusted precisely because it was not
fixed-rate, and for any source whose tail runs longer than one frame duration it
puts the final frame's display slot in the past. The final frame is then stale
before it has been shown.

These tests pin the invariant that replaces it::

    target_media_time is total over [0, N] and non-decreasing, and every value
    comes from the timing model in force

so that a decoded frame is classified stale only when a real later display slot
has begun, never merely because its successor has no timestamp. EOF detection
is a separate concern and is checked separately: these tests use readers that
do end, and assert the final frame is presented *before* that EOF is observed.
"""

import itertools

import pytest

from src.framesel import FrameSelector
from src.timing import FrameClock


class FakeTime:
    """Deterministic monotonic clock; sleeping advances it exactly."""

    def __init__(self, start=100.0):
        self.t = start
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


class ListReader:
    """Reader serving a fixed list of frames, then EOF."""

    def __init__(self, count, timestamps=None, width=4, height=4):
        self._frames = [bytes(4 * 4 * 3)] * count
        self.media_timestamps = timestamps
        self.width = width
        self.height = height
        self.closed = False

    def read_frame(self):
        if not self._frames:
            return None
        return self._frames.pop(0)

    def close(self):
        self.closed = True


def build(timestamps, count=None, fps=30, start=100.0):
    """A clock and selector wired to a source with ``timestamps``."""
    ft = FakeTime(start)
    clock = FrameClock(fps, now=ft.now, sleep_fn=ft.sleep)
    clock.start()
    clock.set_media_timestamps(timestamps)
    reader = ListReader(len(timestamps) if count is None else count, timestamps)
    return ft, clock, FrameSelector(reader, clock), reader


def drain(ft, clock, selector, pace=True):
    """Present every frame the selector yields, pacing to each deadline.

    Returns the list of presented source indices. This mirrors what ``run()``
    does, so the only thing under test is the clock's boundary semantics.
    """
    presented = []
    while True:
        frame, index = selector.next()
        if frame is None:
            return presented
        if pace:
            clock.wait_until(clock.deadline(index))
        presented.append(index)


# ---------------------------------------------------------------------------
# The invariant itself
# ---------------------------------------------------------------------------


def test_target_is_total_and_non_decreasing_past_the_last_frame():
    """``T`` is defined at ``len(T)`` and never steps backwards."""
    timestamps = (0.0, 0.033, 0.066, 0.500, 0.533)
    _, clock, _, _ = build(timestamps, fps=30)
    values = [clock.target_media_time(i) for i in range(len(timestamps) + 4)]
    assert all(b >= a for a, b in itertools.pairwise(values)), values
    assert values[0] == pytest.approx(0.0)


def test_past_the_last_frame_the_source_timeline_continues():
    """The out-of-range answer extends the source's own last gap."""
    timestamps = (0.0, 0.040, 0.080, 0.140)
    _, clock, _, _ = build(timestamps, fps=10)
    # Last timestamp 0.140 plus the source's own last gap of 0.060.
    assert clock.target_media_time(4) == pytest.approx(0.200)
    # Not the fixed-FPS grid, which would have said 0.4.
    assert clock.target_media_time(4) != pytest.approx(4 / 10)


def test_a_timeline_too_short_to_extrapolate_keeps_the_fixed_fps_schedule():
    """A single timestamp has no inter-frame gap, so nothing changes."""
    _, clock, _, _ = build((0.0,), fps=30)
    assert clock.target_media_time(1) == pytest.approx(1 / 30)


# ---------------------------------------------------------------------------
# 1-2. Final PTS above / below the fixed-FPS equivalent
# ---------------------------------------------------------------------------


def test_vfr_final_pts_above_fixed_fps_equivalent_presents_the_last_frame():
    """Shape 1: the tail runs longer than the fps grid."""
    timestamps = (0.0, 0.033, 0.500, 0.533)
    assert timestamps[-1] > len(timestamps) / 30  # the fixed-FPS trap
    ft, clock, selector, _ = build(timestamps, fps=30)
    assert drain(ft, clock, selector) == [0, 1, 2, 3]


def test_vfr_final_pts_below_fixed_fps_equivalent_presents_the_last_frame():
    """Shape 2: a fast tail, where the old fallback happened to look right."""
    timestamps = (0.0, 0.020, 0.040, 0.055)
    assert timestamps[-1] < len(timestamps) / 30
    ft, clock, selector, _ = build(timestamps, fps=30)
    assert drain(ft, clock, selector) == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# 3-4. Large and small final-frame gaps
# ---------------------------------------------------------------------------


def test_large_final_frame_gap_still_presents_the_final_frame():
    """Shape 3: a very long last frame -- the worst case for the old fallback.

    ``target_media_time(4)`` used to be 4/30 = 0.133, which frame 2 was already
    past by the time frame 3 arrived at 1.0 s.
    """
    timestamps = (0.0, 0.033, 0.066, 1.000)
    ft, clock, selector, _ = build(timestamps, fps=30)
    assert clock.target_media_time(4) == pytest.approx(1.000 + (1.000 - 0.066))
    assert drain(ft, clock, selector) == [0, 1, 2, 3]


def test_small_final_frame_gap_still_presents_the_final_frame():
    """Shape 4: a long video whose last gap is shorter than one frame."""
    timestamps = tuple(i / 30 for i in range(29)) + (28 / 30 + 0.001,)
    ft, clock, selector, _ = build(timestamps, fps=30)
    assert drain(ft, clock, selector) == list(range(30))


# ---------------------------------------------------------------------------
# 5-6. Degenerate timelines
# ---------------------------------------------------------------------------


def test_single_frame_source_presents_its_only_frame_then_eof():
    """Shape 5: nothing to extrapolate, and nothing to drop."""
    ft, clock, selector, _ = build((0.0,), fps=30)
    assert drain(ft, clock, selector) == [0]


def test_duplicate_final_pts_keeps_a_presentation_and_still_reaches_eof():
    """Shape 6: a zero-duration last frame owns a zero-length slot.

    The final frame shares a timestamp with its predecessor, so it has no
    display window of its own and is dropped -- exactly as a duplicate pair
    behaves in the body of the timeline. The important property is that this is
    now a *consistent* outcome rather than an accident of the fixed-FPS
    fallback, and that the source is still consumed to EOF.
    """
    timestamps = (0.0, 0.033, 0.100, 0.100)
    ft, clock, selector, _ = build(timestamps, fps=30)
    presented = drain(ft, clock, selector)
    assert presented == [0, 1, 2]
    # The duplicate is accounted for, not silently lost.
    assert selector.stats.dropped == 1
    assert selector.stats.decoded == 4
    # EOF is reached and is not itself counted as a drop.
    assert selector.next() == (None, 4)
    assert selector.stats.dropped == 1


# ---------------------------------------------------------------------------
# 7. CFR behaviour must be untouched
# ---------------------------------------------------------------------------


def test_cfr_source_behaviour_is_unchanged():
    """Shape 7: with no trusted timeline, the fixed-FPS schedule is in force."""
    ft, clock, selector, _ = build(None, count=10, fps=30)
    assert drain(ft, clock, selector) == list(range(10))
    assert clock.target_media_time(10) == pytest.approx(10 / 30)


def test_cfr_still_drops_the_final_frame_from_a_real_backlog():
    """A fixed-FPS source that has genuinely fallen behind still sheds its tail.

    This is the behaviour the fix must NOT remove: with a real backlog the last
    frame's fixed-FPS slot really has passed, so dropping it is correct.
    """
    ft, _, selector, _ = build(None, count=10, fps=30)
    selector.next()  # frame 0
    ft.t += 5.0  # a five-second backlog
    presented = [0]
    while True:
        frame, index = selector.next()
        if frame is None:
            break
        presented.append(index)
    assert presented == [0]
    assert selector.stats.dropped == 9


# ---------------------------------------------------------------------------
# 8-9. The whole timeline, not just the last frame
# ---------------------------------------------------------------------------


def test_vfr_source_where_nothing_needs_dropping_drops_nothing():
    """Shape 8: a healthy VFR source is presented end to end.

    Before the fix this reported a non-zero drop count and a catch-up event for
    a perfectly healthy run, which is what a debug operator reads to judge
    playback health.
    """
    timestamps = (0.0, 0.040, 0.080, 0.200, 0.240, 0.280, 0.500)
    ft, clock, selector, _ = build(timestamps, fps=30)
    assert drain(ft, clock, selector) == list(range(7))
    assert selector.stats.dropped == 0
    assert selector.stats.max_burst_dropped == 0
    assert selector.stats.caught_up_events == 0


def test_vfr_earlier_frames_still_drop_legitimately():
    """Shape 9: a real backlog mid-timeline still sheds the right frames."""
    timestamps = (0.0, 0.040, 0.080, 0.120, 0.160, 0.200)
    ft, clock, selector, _ = build(timestamps, fps=30)
    assert drain(ft, clock, selector, pace=False) == [0, 1, 2, 3, 4, 5]

    # A quarter-second backlog genuinely obsoletes the early frames and the
    # whole tail, because the source is only a fifth of a second long.
    ft, clock, selector, _ = build(timestamps, fps=30)
    clock.wait_until(clock.deadline(0))
    ft.t += 0.25
    assert selector.stale(1, clock.current_time()) is True
    assert selector.stale(5, clock.current_time()) is True
    # And a small backlog drops nothing at all, including the final frame.
    ft, clock, selector, _ = build(timestamps, fps=30)
    clock.wait_until(clock.deadline(0))
    ft.t += 0.01
    assert selector.stale(5, clock.current_time()) is False


# ---------------------------------------------------------------------------
# 10. EOF right after the final frame
# ---------------------------------------------------------------------------


def test_eof_immediately_after_the_final_frame_presentation():
    """Shape 10: the final frame is presented, and then EOF is observed.

    ``run()`` presents each frame and *then* calls ``next()`` again, so the
    final frame's presentation and the EOF that follows it are separate steps.
    """
    timestamps = (0.0, 0.033, 0.500, 0.533)
    ft, clock, selector, reader = build(timestamps, fps=30)
    assert drain(ft, clock, selector) == [0, 1, 2, 3]
    # EOF is reported with the index one past the last frame, and no drop.
    assert selector.next() == (None, 4)
    assert selector.stats.decoded == 4
    assert selector.stats.rendered == 4
    assert selector.stats.dropped == 0
    reader.close()
    assert reader.closed is True


def test_a_short_reader_tail_keeps_the_source_cadence():
    """Frames decoded beyond the PTS list stay on the source's own cadence.

    The boundary answer continues the trusted timeline rather than reverting to
    the fixed-FPS grid, so a reader that outruns its own timeline is paced by
    the source instead of being handed a value from a different model.
    """
    timestamps = (0.0, 0.100, 0.200)
    ft, clock, selector, _ = build(timestamps, count=8, fps=30)
    presented = drain(ft, clock, selector, pace=False)
    assert presented == list(range(8))
    # Frames 3..7 continue the source's 0.1 s cadence from the final timestamp.
    assert clock.target_media_time(3) == pytest.approx(0.300)
    assert clock.target_media_time(4) == pytest.approx(0.400)
    assert clock.target_media_time(3) != pytest.approx(3 / 30)
