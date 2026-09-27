"""Tests for the M3 FrameClock: absolute monotonic timing model.

All tests use a deterministic fake time source and a recording no-op sleep so
they do not rely on real wall-clock behavior.
"""

import time

import pytest

from src.timing import FrameClock


class FakeTime:
    """Deterministic monotonic clock controllable by the test."""

    def __init__(self, start=100.0):
        self.t = start
        self.slept = []

    def now(self):
        return self.t

    def advance(self, delta):
        self.t += delta

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds  # sleeping advances the fake clock


def _clock(fps, fake: FakeTime):
    return FrameClock(fps, now=fake.now, sleep_fn=fake.sleep)


# Test 1 — Frame duration
def test_frame_duration():
    assert FrameClock(30).frame_duration == pytest.approx(1 / 30)
    assert FrameClock(60).frame_duration == pytest.approx(1 / 60)


# Test 2 — Absolute deadlines
def test_absolute_deadlines_no_drift():
    fake = FakeTime(start=100.0)
    clock = _clock(30, fake)
    clock.start()
    assert clock.deadline(0) == pytest.approx(100.0)
    assert clock.deadline(1) == pytest.approx(100.0 + 1 / 30)
    assert clock.deadline(2) == pytest.approx(100.0 + 2 / 30)
    assert clock.deadline(3) == pytest.approx(100.0 + 3 / 30)


# Test 3 — Deadline independence (a late frame does not shift later deadlines)
def test_deadline_independence_after_late_frame():
    fake = FakeTime(start=100.0)
    clock = _clock(30, fake)
    clock.start()
    # Frame 0's deadline is what the schedule says regardless of pacing.
    d2_before = clock.deadline(2)
    # Simulate frame 0 taking a long time and being late.
    fake.advance(0.5)
    clock.wait_until(clock.deadline(0), proc_start=99.95)
    assert clock.stats.late_frames == 1
    # Frame 2's absolute deadline is unchanged by frame 0's lateness.
    assert clock.deadline(2) == pytest.approx(d2_before)


# Test 4 — Early frame: waits for the remaining budget
def test_early_frame_sleeps():
    fake = FakeTime(start=100.0)
    clock = _clock(30, fake)
    clock.start()
    # Frame 1 is due at 100.0333; we finish its work after only 5ms.
    fake.advance(0.005)
    clock.wait_until(clock.deadline(1), proc_start=100.0)
    # It slept exactly the remaining budget of the interval.
    assert fake.slept == [pytest.approx(1 / 30 - 0.005)]
    assert clock.stats.late_frames == 0


# Test 5 — On-time frame: no unnecessary sleep
def test_on_time_frame_no_sleep():
    fake = FakeTime(start=100.0)
    clock = _clock(30, fake)
    clock.start()
    clock.wait_until(clock.deadline(0), proc_start=100.0)
    # At exactly the deadline: no sleep, not late.
    assert fake.slept == []
    assert clock.stats.late_frames == 0
    assert clock.stats.max_lateness == 0.0


# Test 6 — Late frame: sleeps 0, records lateness, continues
def test_late_frame_records_lateness():
    fake = FakeTime(start=100.0)
    clock = _clock(30, fake)
    clock.start()
    fake.advance(0.050)  # render took 50ms > frame-0 deadline of 100.0
    lateness = clock.wait_until(clock.deadline(0), proc_start=100.0)
    assert fake.slept == []       # nothing left to sleep
    assert lateness == pytest.approx(0.050)
    assert clock.stats.late_frames == 1
    assert clock.stats.max_lateness == pytest.approx(0.050)


# Test 7 — Monotonic behavior: default source is a monotonic clock
def test_default_clock_is_monotonic():
    clock = FrameClock(30)
    assert clock._now is time.perf_counter  # unchanged by wall-clock edits
    a = clock.current_time()
    b = clock.current_time()
    assert b >= a


# Test 8 — Statistics
def test_statistics():
    fake = FakeTime(start=100.0)
    clock = _clock(30, fake)
    clock.start()

    # Frame 0: presented exactly on-time at deadline(0) = 100.0.
    clock.wait_until(clock.deadline(0), proc_start=100.0 - 0.005)

    # Frame 1: force being 20ms past deadline(1); 8ms of processing.
    deadline1 = clock.deadline(1)              # 100.03333...
    fake.t = deadline1 + 0.020
    clock.wait_until(clock.deadline(1), proc_start=fake.t - 0.008)

    r = clock.report()
    assert r["frame_count"] == 2
    assert r["late_frames"] == 1
    assert r["target_fps"] == 30
    assert r["max_lateness_ms"] == pytest.approx(20.0, abs=0.001)
    assert r["avg_lateness_ms"] == pytest.approx(20.0 / 2, abs=0.001)
    # 8ms and 5ms of processing across the two frames.
    assert r["avg_processing_ms"] == pytest.approx((8.0 + 5.0) / 2, abs=0.001)
    assert r["achieved_fps"] > 0


# Test 1 (original) — negative FPS rejected
def test_negative_fps_rejected():
    with pytest.raises(ValueError):
        FrameClock(0)


# Lateness below the threshold is not counted as a late frame
def test_subthreshold_lateness_is_on_time():
    fake = FakeTime(start=100.0)
    clock = _clock(30, fake)
    clock.start()
    # Presented 1ms past the deadline — under the 2ms default threshold.
    fake.t = clock.deadline(0) + 0.001
    clock.wait_until(clock.deadline(0), proc_start=100.0)
    assert clock.stats.late_frames == 0
    assert clock.stats.on_time_frames == 1



def test_media_clock_controls_wait_target():
    from src.timing import FrameClock

    class FakeTime:
        def __init__(self):
            self.t = 0.0
            self.sleeps = []

        def now(self):
            return self.t

        def sleep(self, seconds):
            self.sleeps.append(seconds)
            self.t += seconds

    ft = FakeTime()
    media = [0.0]
    clock = FrameClock(10, now=ft.now, sleep_fn=ft.sleep)
    clock.start()
    clock.set_media_clock(lambda: media[0])
    # set_media_clock alone does not make the clock authoritative -- adoption is
    # explicit, so wait_until actually takes its media-clock branch here.
    assert clock.adopt_media_clock() is True
    clock.wait_until(clock.deadline(1))
    assert ft.sleeps == [pytest.approx(0.1)]
    assert clock.stats.frame_count == 1


def test_media_clock_none_falls_back_to_absolute_deadline():
    class FakeTime:
        def __init__(self):
            self.t = 0.0
            self.sleeps = []

        def now(self):
            return self.t

        def sleep(self, seconds):
            self.sleeps.append(seconds)
            self.t += seconds

    ft = FakeTime()
    clock = FrameClock(10, now=ft.now, sleep_fn=ft.sleep)
    clock.start()
    clock.set_media_clock(lambda: None)
    clock.wait_until(clock.deadline(1))
    assert ft.sleeps == [pytest.approx(0.1)]



def test_media_timestamps_override_fixed_fps_targets():
    clock = FrameClock(10, now=lambda: 0.0, sleep_fn=lambda _: None)
    clock.start(0.0)
    clock.set_media_timestamps((0.0, 0.04, 0.08, 0.14))
    assert clock.target_media_time(0) == pytest.approx(0.0)
    assert clock.target_media_time(1) == pytest.approx(0.04)
    assert clock.target_media_time(3) == pytest.approx(0.14)
    # Past the final frame the answer continues the source's own timeline at the
    # source's own last inter-frame duration (0.14 + 0.06 = 0.20), NOT the
    # fixed-FPS grid, which would have said 0.4 and placed the final frame's
    # display slot in the past.
    assert clock.target_media_time(4) == pytest.approx(0.20)
    assert clock.target_media_time(5) == pytest.approx(0.26)


# The deadline is what actually paces playback, so it must follow the source
# timestamps rather than the fixed frame duration.
def test_deadline_follows_source_timestamps():
    clock = FrameClock(30, now=lambda: 0.0, sleep_fn=lambda _: None)
    clock.start(100.0)
    clock.set_media_timestamps((0.0, 0.04, 0.50))
    assert clock.deadline(0) == pytest.approx(100.0)
    assert clock.deadline(1) == pytest.approx(100.04)
    assert clock.deadline(2) == pytest.approx(100.50)


# Without a trusted timeline the fixed-FPS schedule is unchanged.
def test_deadline_without_timestamps_still_uses_fixed_fps():
    clock = FrameClock(30, now=lambda: 0.0, sleep_fn=lambda _: None)
    clock.start(100.0)
    assert clock.deadline(1) == pytest.approx(100.0 + 1 / 30)


# Variable frame durations reach the sleep, not just the reported targets:
# these are the irregular gaps of a real VFR source.
def test_variable_rate_pacing_sleeps_to_source_timestamps():
    fake = FakeTime(start=0.0)
    clock = _clock(30, fake)
    clock.start(0.0)
    clock.set_media_timestamps((0.0, 0.033, 0.100, 0.500))
    for index in range(4):
        clock.wait_until(clock.deadline(index))
    assert fake.slept == pytest.approx([0.033, 0.067, 0.400])


# The media clock and the monotonic deadline must pace against the same
# canonical target, so both branches sleep for identical amounts.
def test_media_clock_and_deadline_agree_on_variable_rate_target():
    fake = FakeTime(start=0.0)
    media = [0.0]
    clock = _clock(30, fake)
    clock.start(0.0)
    clock.set_media_timestamps((0.0, 0.200))
    clock.set_media_clock(lambda: media[0])
    # Adopted, so this exercises the media-clock branch of wait_until rather
    # than silently falling through to the identical `else` branch.
    assert clock.adopt_media_clock() is True
    clock.wait_until(clock.deadline(1))
    assert fake.slept == pytest.approx([0.200])


# The media-clock branch of wait_until targets `deadline - media_now` rather than
# the absolute deadline, so a clock that disagrees with the monotonic basis moves
# the sleep. This is the only direct coverage of that branch.
def test_media_clock_branch_retargets_the_sleep():
    fake = FakeTime(start=0.0)
    media = [0.15]
    clock = _clock(30, fake)
    clock.start(0.0)
    clock.set_media_clock(lambda: media[0])
    assert clock.adopt_media_clock() is True
    # deadline(1) is start + 1/30 = 0.0333; media says 0.15 has already
    # elapsed, so the frame is already overdue and nothing should be slept.
    clock.wait_until(clock.deadline(1))
    assert fake.slept == []


# Every fake clock in the suite sleeps exactly what it is asked, so the lateness
# path that a real scheduler exercises has no coverage. The threshold exists for
# exactly this, so drive it.
def test_oversleep_is_recorded_as_lateness():
    class DriftingTime:
        def __init__(self):
            self.t = 0.0
            self.drift = 0.0

        def now(self):
            return self.t

        def sleep(self, seconds):
            self.t += seconds + self.drift

    ft = DriftingTime()
    clock = FrameClock(10, now=ft.now, sleep_fn=ft.sleep)
    clock.start(0.0)
    clock.wait_until(clock.deadline(0))  # on time
    ft.drift = 0.01
    lateness = clock.wait_until(clock.deadline(1))  # oversleeps by 10 ms
    assert lateness == pytest.approx(0.01)
    assert clock.stats.late_frames == 1
    assert clock.stats.on_time_frames == 1
    assert clock.report()["max_lateness_ms"] == pytest.approx(10.0)


# A late frame must not shift later deadlines off the source timeline.
def test_variable_rate_deadlines_are_independent_of_lateness():
    fake = FakeTime(start=0.0)
    clock = _clock(30, fake)
    clock.start(0.0)
    clock.set_media_timestamps((0.0, 0.033, 0.100, 0.500))
    before = [clock.deadline(i) for i in range(4)]
    fake.advance(0.250)  # badly late; the schedule must not move
    assert [clock.deadline(i) for i in range(4)] == pytest.approx(before)
