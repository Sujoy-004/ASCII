"""Frame timing: an absolute monotonic video playback clock.

Frame N is scheduled to be *presented* at an absolute timeline deadline:

    deadline = playback_start + N × frame_duration

rather than chaining each frame off the previous sleep. This makes the clock
resistant to accumulated drift: a late frame does not shift later frames'
target deadlines off the original timeline. This is the foundation for later
audio/video synchronization (M5).

The clock uses a monotonic high-resolution time source (time.perf_counter by
default) so wall-clock adjustments cannot affect playback timing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

ClockFn = Callable[[], float]
SleepFn = Callable[[float], None]


@dataclass
class TimingStats:
    """Accumulated playback timing metrics (values in seconds)."""

    frame_count: int = 0
    # A frame is "late" when it is presented after its absolute deadline.
    late_frames: int = 0
    on_time_frames: int = 0
    total_lateness: float = 0.0  # sum of positive lateness (early adds 0)
    max_lateness: float = 0.0
    total_processing: float = 0.0  # time spent reading/rendering/writing
    total_pacing: float = 0.0  # sum of intervals between consecutive frames


class FrameClock:
    """Paces playback on an absolute timeline using a monotonic clock.

    Injection points (defaults match production behavior but allow
    deterministic unit testing):

    - `now`: monotonic time source callable returning seconds.
    - `sleep_fn`: blocking sleep callable for the remaining frame budget.
    """

    def __init__(
        self,
        target_fps: int,
        now: ClockFn | None = None,
        sleep_fn: SleepFn | None = None,
        late_threshold: float = 0.002,
    ) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be positive")
        self.target_fps = target_fps
        self.frame_duration = 1.0 / target_fps
        # Below this lateness (default 2ms) a frame is considered on time;
        # time.sleep() typically wakes a fraction of a millisecond late, so
        # we do not count that as a genuinely late frame.
        self.late_threshold = late_threshold
        self._now = now if now is not None else time.perf_counter
        self._sleep = sleep_fn if sleep_fn is not None else time.sleep
        self.stats = TimingStats()
        self._start_time: float | None = None
        self._last_presented: float | None = None

    @staticmethod
    def frame_budget(target_fps: int) -> float:
        """Per-frame time budget in seconds for a target FPS."""
        return 1.0 / target_fps

    @property
    def start_time(self) -> float:
        """The playback start time (only valid after start())."""
        if self._start_time is None:
            raise RuntimeError("clock.start() must be called first")
        return self._start_time

    def current_time(self) -> float:
        """Read the current monotonic time."""
        return self._now()

    def start(self, start_time: float | None = None) -> None:
        """Begin the playback timeline and reset accumulated statistics.

        ``start_time`` seeds the absolute zero of the timeline. When omitted,
        the current monotonic time is used. Passing an external value lets the
        video schedule share a single ``playback_start`` with the audio
        timeline (master-clock synchronization, M5).
        """
        self.stats = TimingStats()
        self._last_presented = None
        self._start_time = start_time if start_time is not None else self._now()

    def deadline(self, frame_index: int) -> float:
        """Absolute presentation deadline for the given frame index.

        Derived purely from the playback start and the fixed frame duration,
        independent of how earlier frames were actually paced.
        """
        return self.start_time + frame_index * self.frame_duration

    def wait_until(self, deadline: float, proc_start: float | None = None) -> float:
        """Present the current frame at (or as near as possible to) `deadline`.

        Optionally records the processing time measured from `proc_start`
        (captured before this frame's read/render/work), then sleeps only for
        the remaining budget, then measures the actual lateness
        (positive means late, non-positive means early/on-time).

        Returns the measured lateness in seconds.
        """
        now = self._now()
        if proc_start is not None:
            self.stats.total_processing += now - proc_start

        remaining = deadline - now
        if remaining > 0:
            self._sleep(remaining)

        presented = self._now()
        if self._last_presented is not None:
            self.stats.total_pacing += presented - self._last_presented
        self._last_presented = presented

        lateness = presented - deadline
        self.stats.frame_count += 1
        if lateness > self.late_threshold:
            self.stats.late_frames += 1
            self.stats.total_lateness += lateness
            if lateness > self.stats.max_lateness:
                self.stats.max_lateness = lateness
        elif lateness > 0:
            # Late by less than the threshold: record nothing as late.
            self.stats.on_time_frames += 1
        else:
            # Early / exactly on time.
            self.stats.on_time_frames += 1
        return lateness

    def report(self) -> dict[str, float | int]:
        """Summarize playback timing (used by debug output)."""
        s = self.stats
        elapsed = self.current_time() - self.start_time
        achieved = s.frame_count / elapsed if elapsed > 0 else 0.0
        return {
            "target_fps": self.target_fps,
            "frame_duration_ms": self.frame_duration * 1000,
            "frame_count": s.frame_count,
            "elapsed_s": elapsed,
            "achieved_fps": achieved,
            "avg_processing_ms": ((s.total_processing / s.frame_count) * 1000
                                  if s.frame_count else 0.0),
            "avg_pacing_ms": ((s.total_pacing / (s.frame_count - 1)) * 1000
                              if s.frame_count > 1 else 0.0),
            "avg_lateness_ms": ((s.total_lateness / s.frame_count) * 1000
                                if s.frame_count else 0.0),
            "max_lateness_ms": s.max_lateness * 1000,
            "late_frames": s.late_frames,
            "on_time_frames": s.on_time_frames,
        }
