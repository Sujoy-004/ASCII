"""Frame timing: an absolute monotonic video playback clock.

Frame N is scheduled to be *presented* at an absolute timeline deadline:

    deadline = playback_start + target_media_time(N)

rather than chaining each frame off the previous sleep. This makes the clock
resistant to accumulated drift: a late frame does not shift later frames'
target deadlines off the original timeline. When an external media clock is
available, presentation can instead be paced against that clock on each frame.

``target_media_time`` is the one frame-index-to-media-time path: source
presentation timestamps when the probed timeline was trusted, fixed-FPS timing
otherwise, so a variable-rate source keeps its own frame durations. It is
non-decreasing, and it stays total past the final frame -- a frame can only be
judged stale when a real later display slot has begun, never merely because its
successor has no timestamp.

The clock runs on one of three explicitly-tracked sources (``clock_source``):

- ``MONOTONIC``: playback time is ``now - start_time``.
- ``FFPLAY_AUDIO``: FFplay reports the audio master's media position, which is
  authoritative for pacing.
- ``FALLBACK_AFTER_AUDIO_FAILURE``: FFplay stopped reporting, so pacing has
  returned to the monotonic basis.

Both transitions rebase ``start_time`` (``rebase_to_media``) so that media time
is continuous across the change: 12.350 s of media time immediately before the
switch is 12.350 s immediately after it, not some unrelated value the new basis
happens to imply. Switching clock source therefore never introduces a
scheduling step.

The clock uses a monotonic high-resolution time source (time.perf_counter by
default) so wall-clock adjustments cannot affect playback timing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

MediaClockFn = Callable[[], float | None]

ClockFn = Callable[[], float]
SleepFn = Callable[[float], None]

# Authoritative clock sources, reported verbatim in debug output.
MONOTONIC = "monotonic"
FFPLAY_AUDIO = "ffplay-audio"
FALLBACK_AFTER_AUDIO_FAILURE = "fallback-after-audio-failure"


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
        self._media_clock: MediaClockFn | None = None
        self._media_timestamps: tuple[float, ...] | None = None
        # Authoritative clock source, updated on every transition. This is the
        # runtime truth; debug output reports it rather than a separate guess.
        self.clock_source: str = MONOTONIC
        self._last_media_time: float | None = None
        self._last_media_time_at: float | None = None

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
        the current monotonic time is used. Callers should call this *after* the
        decoder has produced its first frame, so the origin is the earliest
        instant at which a frame could actually be presented; that is what
        keeps process startup latency out of the frame budget.

        Passing an external value seeds the origin explicitly instead.
        """
        self.stats = TimingStats()
        self._last_presented = None
        self._start_time = start_time if start_time is not None else self._now()
        self._media_clock = None
        self._media_timestamps = None
        self.clock_source = MONOTONIC
        self._last_media_time = None
        self._last_media_time_at = None

    def set_media_clock(self, media_clock: MediaClockFn | None) -> None:
        """Use an external media clock as the presentation-time reference."""
        self._media_clock = media_clock

    def rebase_to_media(self, media_time: float, now: float | None = None) -> None:
        """Re-derive the timeline origin so media time is continuous at ``now``.

        ``start_time`` always means "the monotonic instant at which media time
        was zero". Setting it to ``now - media_time`` makes the monotonic basis
        agree with the media basis at this instant, so adopting or abandoning a
        media clock costs no scheduling step.
        """
        if now is None:
            now = self._now()
        self._start_time = now - media_time

    def _read_media_clock(self) -> float | None:
        """Sample the external media clock, or None when it cannot be read."""
        if self._media_clock is None:
            return None
        try:
            return self._media_clock()
        except (OSError, RuntimeError, ValueError):
            return None

    def adopt_media_clock(self) -> bool:
        """Make the external media clock authoritative, if it is usable now.

        Called once at the startup settle, not per frame. Adoption is
        deliberately explicit rather than automatic: a media clock that only
        becomes readable *after* playback has begun may be reporting a position
        ahead of the video, and adopting it then would retroactively mark the
        first frames stale. That would turn FFplay's own startup latency into a
        burst of dropped frames, which is exactly the misclassification this
        clock avoids. If the media clock is not ready at the settle, playback
        stays on the monotonic basis for the whole run.

        Returns True when the media clock was adopted.
        """
        if self._media_clock is None or self._start_time is None:
            return False
        value = self._read_media_clock()
        if value is None:
            return False
        self._last_media_time = value
        self._last_media_time_at = self._now()
        self.rebase_to_media(value)
        self.clock_source = FFPLAY_AUDIO
        return True

    def media_time(self) -> float | None:
        """Return the current media time, when the media clock is authoritative.

        Returns None unless ``clock_source`` is ``FFPLAY_AUDIO``, so callers
        fall back to the monotonic basis. That gate is what makes the source
        explicit: a media clock that was never adopted, or one that was adopted
        and has since stopped reporting, cannot influence a single decision.

        An adopted clock that goes silent triggers the one automatic
        transition, to ``FALLBACK_AFTER_AUDIO_FAILURE``, rebased onto where the
        clock stood at this instant so the change of source costs no step.
        """
        if self.clock_source != FFPLAY_AUDIO:
            return None
        value = self._read_media_clock()
        if value is None:
            # The adopted clock went away. Anchor the monotonic basis to where
            # that clock stood at this instant -- the last sample plus the time
            # it would have advanced since -- so media time carries on across
            # the change of source instead of jumping.
            if self._last_media_time is not None:
                now = self._now()
                elapsed = now - (self._last_media_time_at or now)
                self.rebase_to_media(
                    self._last_media_time + max(0.0, elapsed), now
                )
            self.clock_source = FALLBACK_AFTER_AUDIO_FAILURE
            return None
        self._last_media_time = value
        self._last_media_time_at = self._now()
        return value

    def set_media_timestamps(self, timestamps: tuple[float, ...] | None) -> None:
        """Use source frame presentation timestamps when available."""
        self._media_timestamps = timestamps

    def target_media_time(self, frame_index: int) -> float:
        """Return the canonical media presentation time for a frame index.

        This is the single frame-index-to-media-time path, and it is
        non-decreasing in ``frame_index``:

        - ``0 <= frame_index < len(timestamps)``: the source's own normalized
          presentation timestamp, so a variable-rate source keeps its frame
          durations.
        - ``frame_index >= len(timestamps)`` on a trusted timeline: the display
          schedule continued at the source's own final inter-frame duration,
          starting one duration after the last real timestamp. No such frame
          exists, so ``frame_index == len(timestamps)`` is a lower bound on where
          the media ends rather than a frame's presentation time, but it is what
          gives the final frame a real display window. Callers ask when frame
          ``n + 1``'s slot begins; answering from the fixed-FPS grid here would
          place that instant in the past for any source whose tail runs longer
          than one frame duration, which drops the final frame unconditionally.
        - No trusted timeline, a negative index, or fewer than two timestamps
          (no gap to extrapolate from): the fixed-FPS schedule,
          ``frame_index * frame_duration``, unchanged.

        Every value therefore comes from the timing model actually in force, so a
        decoded frame can be classified stale only when a real later display
        slot has begun -- never merely because its successor has no timestamp.
        """
        timestamps = self._media_timestamps
        if timestamps is not None and 0 <= frame_index < len(timestamps):
            return timestamps[frame_index]
        if timestamps is not None and frame_index >= len(timestamps) >= 2:
            gap = timestamps[-1] - timestamps[-2]
            return timestamps[-1] + (frame_index - len(timestamps) + 1) * gap
        return frame_index * self.frame_duration

    def deadline(self, frame_index: int) -> float:
        """Absolute presentation deadline for the given frame index.

        Derived from the playback start and the canonical target media time, so
        a variable-rate source paces to its own timestamps. Still independent
        of how earlier frames were actually paced.
        """
        return self.start_time + self.target_media_time(frame_index)

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

        wait_target = deadline
        media_now = self.media_time()
        if media_now is not None:
            media_target = deadline - self.start_time
            remaining = media_target - media_now
            wait_target = now + remaining
        else:
            remaining = deadline - now

        if remaining > 0:
            self._sleep(remaining)

        presented = self._now()
        if self._last_presented is not None:
            self.stats.total_pacing += presented - self._last_presented
        self._last_presented = presented

        lateness = presented - wait_target
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
        # An unstarted clock reports a zero-length run rather than raising: the
        # decoder can be interrupted while warming up, before the origin exists.
        elapsed = self.current_time() - (
            self._start_time if self._start_time is not None else self._now()
        )
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
