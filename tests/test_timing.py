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
    assert FrameClock.frame_budget(30) == pytest.approx(1 / 30)
    assert FrameClock.frame_budget(60) == pytest.approx(1 / 60)
    assert FrameClock(30).frame_duration == pytest.approx(1 / 30)


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
