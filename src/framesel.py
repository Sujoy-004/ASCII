"""Milestone 6: frame selection / real-time lag recovery.

The FFmpeg rawvideo pipe delivers frames faster than real time and the master
playback timeline (M5) is authoritative. When processing falls behind, a frame
whose intended presentation time has already fully passed (i.e. the *next*
frame slot has begun) is obsolete: rendering it only pushes the display
further behind the shared timeline.

M6 therefore reads every decoded frame (to keep the pipe drained -- dropping
is discarding already-read bytes, never backpressuring FFmpeg) and, before
rendering, drops frames that are already stale, converging back toward the
current media time instead of presenting stale content indefinitely.

Design rules honored here:
 - Absolute deadlines remain authoritative (deadline(n) = start + n * duration);
   dropping frame n does NOT shift frame n+1.
 - No unbounded queue: every decoded frame is either rendered immediately or
   discarded immediately; nothing is buffered for later.
 - No arbitrary "drop every Nth" and no "drop if processing > X ms" rule; a
   frame is stale purely relative to the timeline.
 - The first frame is always rendered so process startup does not trigger an
   aggressive, content-empty catch-up burst (startup policy).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DropStats:
    """Decoded / rendered / dropped accounting plus catch-up metrics.

    Every frame read from the FFmpeg pipe is *decoded*. A frame is *rendered*
    only if it is presented; a decoded-but-not-rendered frame was *dropped*
    (not "missing" or "failed").
    """

    decoded: int = 0
    rendered: int = 0
    caught_up_events: int = 0
    max_burst_dropped: int = 0
    _running_burst: int = field(default=0, repr=False)

    @property
    def dropped(self) -> int:
        return self.decoded - self.rendered

    @property
    def drop_rate(self) -> float:
        return (self.dropped / self.decoded * 100.0) if self.decoded else 0.0

    def record_drop(self) -> None:
        """Note one dropped frame and extend/count the current catch-up burst."""
        self._running_burst += 1
        if self._running_burst == 1:
            self.caught_up_events += 1
        self.max_burst_dropped = max(self.max_burst_dropped, self._running_burst)

    def end_burst(self) -> None:
        """Reset the running burst (a burst ends when a frame is rendered)."""
        self._running_burst = 0

    def report(self) -> dict[str, int | float]:
        return {
            "decoded": self.decoded,
            "rendered": self.rendered,
            "dropped": self.dropped,
            "drop_rate": self.drop_rate,
            "caught_up_events": self.caught_up_events,
            "max_burst_dropped": self.max_burst_dropped,
        }


class FrameSelector:
    """Selects which decoded frames to present, dropping stale ones.

    Wraps a frame ``reader`` and consults a ``clock`` that owns the master
    timeline (``deadline(n)`` and ``current_time()``). ``next()`` yields the
    next frame worth presenting (or None on EOF), having stripped any stale
    frames that precede it.
    """

    def __init__(self, reader, clock) -> None:
        self.reader = reader
        self.clock = clock
        self.stats = DropStats()
        self._first = True
        self._source_index = 0

    def stale(self, frame_index: int, now: float) -> bool:
        """True if a decoded frame is already obsolete.

        A frame is stale once the presentation slot of the following frame has
        begun: ``now >= deadline(frame_index + 1)``. Small lateness within one
        display period (normal OS scheduling jitter) is therefore still
        rendered; only a frame that is at least a full frame behind the
        timeline is dropped. No arbitrary millisecond constant is used.
        """
        media_now = self.clock.media_time()
        if media_now is not None:
            return media_now >= self.clock.target_media_time(frame_index + 1)
        return now >= self.clock.deadline(frame_index + 1)

    def next(self):
        """Return the next frame to render, dropping stale frames first.

        Reads and discards stale frames as fast as they arrive (draining the
        FFmpeg pipe so it never backs up), then returns the first useful frame.
        Returns ``(None, last_source_index)`` at EOF. Frame indices are the
        source FFmpeg indices (0, 1, 2, ...) used to compute absolute
        deadlines; they are independent of how many were dropped/rendered.
        """
        while True:
            frame = self.reader.read_frame()
            if frame is None:
                return None, self._source_index
            idx = self._source_index
            self._source_index += 1
            self.stats.decoded += 1

            if self._first:
                # Startup policy (M6): always present the very first frame so
                # process-launch skew does not trigger an empty catch-up burst.
                self._first = False
                self.stats.rendered += 1
                self.stats.end_burst()
                return frame, idx

            if self.stale(idx, self.clock.current_time()):
                self.stats.record_drop()
                continue  # discarded; inspect the next decoded frame

            self.stats.rendered += 1
            self.stats.end_burst()
            return frame, idx
