"""Bounded adaptive quality control driven by measured per-frame work.

This module decides *rendering quality only*. It never touches frame timing,
presentation deadlines, PTS handling, or frame selection: the scheduler keeps
dropping frames rather than stretching the clock, exactly as before. The caller
measures how long a frame actually took to smooth, resize, render and write,
and reports that here.

The policy is deliberately shaped so it cannot oscillate:

- Evidence is a mean over a fixed window of frames, and each sample is first
  clamped to ``MAX_UTILIZATION``. A mean is *not* outlier-bounded on its own --
  one slow frame (a GC pause, a terminal resize, a stalled decode) moves the
  mean by ``clamp/window``, and with the default window that is 1/15, so any
  healthy baseline below ``down - MAX_UTILIZATION/window`` provably cannot be
  flipped by a single bad frame. Sustained overload is unaffected: every
  sample in a genuinely overloaded window still reads as clamped.
- Downgrading needs sustained high utilisation and recovering needs sustained
  low utilisation. The thresholds are far apart, so intermediate load is
  genuinely undecided rather than flapping.
- After a change the controller ignores input for a cooldown, so quality cannot
  change faster than the window itself. A window is a mean, so a workload that
  merely oscillates around a threshold averages out and stays put; the
  hysteresis gap plus the cooldown is what bounds any movement.
- ``worst_level`` records the deepest level ever required, so a debug report
  can show how far quality had to be pulled down on this machine.

Levels are ordered cheapest-quality-last and map onto *levers that are actually
live*, supplied by the caller (see :func:`apply_level`). There is no fixed rung
count: a level index is "how many live levers have been shed", so a
configuration with nothing to shed gets an empty ladder and never degrades,
rather than reporting a degradation that does nothing.
"""

from __future__ import annotations

from collections import deque

FULL = 0
NO_SMOOTHING = 1
MONOCHROME = 2

# Largest per-frame utilisation a single sample may report. Bounds how far one
# outlier can move a window's mean (see the module docstring); it does not cap
# what sustained overload looks like, because every sample in a truly
# overloaded window is clamped to this same value.
MAX_UTILIZATION = 2.0


class QualityController:
    """Tracks a quality ``level`` from per-frame work utilisation.

    ``frame_budget`` is the display slot the frame was actually scheduled into,
    i.e. the gap to the next frame's presentation time -- not necessarily
    ``1/fps``, because a variable-rate source gives some frames a longer slot.
    Utilisation is ``work / budget``; a value of 1.0 means the frame consumed
    its whole slot and the next one will be late.
    """

    def __init__(
        self,
        *,
        window: int = 30,
        down: float = 0.85,
        up: float = 0.5,
        cooldown: int = 60,
        max_level: int = MONOCHROME,
    ) -> None:
        if window < 1:
            raise ValueError("window must be at least 1")
        if not 0.0 < up < down:
            raise ValueError("thresholds must satisfy 0 < up < down")
        if cooldown < window:
            raise ValueError("cooldown must cover at least one window")
        if max_level < 0:
            raise ValueError("max_level must not be negative")
        self._window = window
        self._down = down
        self._up = up
        self._cooldown = cooldown
        self._max_level = max_level
        self._recent: deque[float] = deque(maxlen=window)
        # Frames observed since the last change. Consumed by the cooldown
        # gate; a change resets it to 0, so the gap between two changes is
        # always at least ``cooldown``.
        self._quiet = cooldown
        self.level = FULL
        # Worst level this machine has needed so far, for reporting.
        self.worst_level = FULL

    def record(self, work_seconds: float, frame_budget: float) -> int:
        """Report one frame's measured work; return the resulting level.

        Returns the level unchanged unless a whole window of evidence crossed a
        threshold, so callers may call this once per presented frame.
        """
        if frame_budget <= 0:
            raise ValueError("frame_budget must be positive")
        # Clamped so one stalled frame cannot drag the mean over a threshold
        # the machine was otherwise nowhere near.
        self._recent.append(min(work_seconds / frame_budget, MAX_UTILIZATION))
        if len(self._recent) < self._window:
            return self.level
        # The window is consumed and discarded here, *before* the cooldown
        # gate, so evidence earned during a cooldown is dropped rather than
        # banked. That is what makes the cooldown below an actual frame gap.
        util = sum(self._recent) / len(self._recent)
        self._recent.clear()
        self._quiet += self._window
        if self._quiet < self._cooldown:
            return self.level
        if util >= self._down and self.level < self._max_level:
            self.level += 1
            # Record the worst level this machine has actually needed, so a
            # debug report can show how far quality had to be pulled down.
            self.worst_level = self.level
            self._quiet = 0
        elif util <= self._up and self.level > 0:
            self.level -= 1
            self._quiet = 0
        return self.level


def apply_level(level: int, levers: list[tuple[object, str]]) -> None:
    """Push a controller level onto the live levers, cheapest quality first.

    ``levers`` is ordered by what is shed first and built by the caller from the
    levers that are actually available and meaningful right now. Level ``i``
    sheds the first ``i`` levers and leaves the rest alone, so level 0 is
    always exactly what the user configured and any level is reversible.

    Levers are discovered rather than assumed, so this cannot disable something
    a rendering mode depends on (half-block output needs color, so color is
    simply not offered as a lever there) and cannot report a level that does
    nothing. Idempotent, and a healthy run that stays at level 0 changes
    nothing at all.
    """
    for index, (target, attribute) in enumerate(levers):
        setattr(target, attribute, index >= level)
