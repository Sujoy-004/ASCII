"""Playback synchronization: a shared master timeline and A/V timing model.

Keeps the three temporal notions the rest of the system must keep distinct:

- wall/process time  -- raw monotonic seconds (time.perf_counter)
- video presentation time -- driven by FrameClock absolute deadlines
- audio playback time -- observed from FFplay's reported audio-master media clock

This module owns the single shared ``playback_start`` reference, the per
subsystem timing observations, audio-status tri-state, and the
end-of-playback completion policy. It does not launch processes or render
video.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum


class AudioStatus(Enum):
    """Tri-state result of audio-stream detection."""

    CONFIRMED = "CONFIRMED"  # ffprobe positively found >=1 audio stream
    ABSENT = "ABSENT"        # ffprobe positively found no audio stream
    UNKNOWN = "UNKNOWN"      # ffprobe unavailable or probing failed


@dataclass
class PlaybackTimeline:
    """Observations along the single shared playback timeline.

    All timestamps are monotonic seconds on the same clock as
    ``playback_start`` (time.perf_counter by default).
    """

    playback_start: float
    # --- video ---
    video_launched_at: float | None = None
    first_frame_at: float | None = None
    video_eof_at: float | None = None
    frame_count: int = 0
    # --- audio ---
    audio_status: AudioStatus = AudioStatus.ABSENT
    audio_launched_at: float | None = None
    audio_exit_at: float | None = None
    last_av_drift: float | None = None
    max_av_drift: float = 0.0
    # --- completion ---
    audio_waited_for_exit: bool = False

    @property
    def video_startup_offset(self) -> float | None:
        """Delay from playback start to the first presented frame."""
        if self.first_frame_at is None:
            return None
        return self.first_frame_at - self.playback_start

    @property
    def audio_startup_offset(self) -> float | None:
        """Delay from playback start to the FFplay process launch."""
        if self.audio_launched_at is None:
            return None
        return self.audio_launched_at - self.playback_start

    @property
    def completion_offset(self) -> float | None:
        """Time from video EOF to audio natural exit (the audible tail)."""
        if self.video_eof_at is None or self.audio_exit_at is None:
            return None
        return self.audio_exit_at - self.video_eof_at


# Safety ceiling (seconds) for the natural-exit wait, covering FFplay's
# process startup plus its decoder/flush after the file is consumed.
#
# This is NOT a presentational delay inserted at EOF. It is an upper bound
# only: FFplay normally exits on its own well inside it (the pre-M5 audit
# measured a ~0.25-0.86s tail beyond video EOF). It prevents waiting forever
# on a hung external process.
FLUSH_GRACE = 2.0


def audio_completion_timeout(
    audio_started_at: float,
    now: float,
    media_duration: float | None,
) -> float:
    """Timeline-based upper bound (seconds) to wait for FFplay natural exit.

    Derived from when audio was launched and the media length, so it is not a
    fixed empirical delay. At video EOF ``now`` is typically near
    ``audio_started_at + media_duration``, leaving roughly ``FLUSH_GRACE`` for
    the residual buffered/flush tail. If the duration is unknown (cannot be
    probed), the grace bound alone is used.
    """
    if media_duration is not None:
        return max(0.0, (audio_started_at + media_duration + FLUSH_GRACE) - now)
    return FLUSH_GRACE


def probe_media_duration(
    video_path: str,
    ffprobe: str | None = None,
) -> float | None:
    """Return the container duration (seconds) via FFprobe.

    Returns None if FFprobe is unavailable, the probe fails, or the value
    cannot be parsed. Callers must treat None as "unknown".
    """
    ffprobe = ffprobe or shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # A non-zero status means the probe failed even if it managed to print
        # something parsable (a truncated or partially readable container, for
        # example). Trusting that output would hand the caller a duration that
        # does not describe the file.
        if result.returncode != 0:
            return None
        text = result.stdout.decode(errors="replace").strip()
        if not text:
            return None
        return float(text)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _trusted_timeline(
    values: list[float], duration: float | None
) -> tuple[float, ...] | None:
    """Normalize raw presentation timestamps, or reject the whole timeline.

    FFprobe emits one row per decoded frame, so the list indexes frames
    positionally. Rejecting the entire timeline (rather than dropping a bad
    entry) is what keeps the list aligned with frame indexes: a skipped entry
    would shift every later frame onto a neighbour's timestamp.

    ``None`` means the caller must use fixed-FPS timing for the whole video.
    """
    if any(not math.isfinite(value) for value in values):
        return None
    # Ordering is checked on the raw values, before normalization, so an
    # out-of-order timestamp cannot hide behind the subtraction.
    if any(after < before for before, after in zip(values, values[1:])):
        return None
    normalized = tuple(value - values[0] for value in values)
    if duration is not None and duration > 0:
        # The last frame belongs near the end of the media. A timeline that
        # ends far earlier describes only part of the file, so trusting it
        # would pace the whole video against a fraction of its real length.
        slack = max(1.0, duration * 0.1)
        if normalized[-1] + slack < duration * 0.9:
            return None
    return normalized


def probe_video_timestamps(
    video_path: str,
    ffprobe: str | None = None,
    duration: float | None = None,
) -> tuple[float, ...] | None:
    """Return normalized video frame timestamps in presentation order.

    FFprobe's best-effort timestamps reflect the decoded video timeline and
    preserve variable frame durations when the source has them. The result is
    normalized so the first timestamp is media time zero. ``None`` means the
    timestamps could not be trusted as a frame-indexed timeline; callers then
    use their fixed-FPS fallback. ``duration`` is the media duration, used to
    reject a timeline that plainly does not describe the same file.
    """
    ffprobe = ffprobe or shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "frame=best_effort_timestamp_time",
                "-of", "csv=p=0",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return None
        values: list[float] = []
        for raw in result.stdout.decode(errors="replace").splitlines():
            text = raw.split(",", 1)[0].strip()
            if not text or text.upper() == "N/A":
                # A row without a value means the remaining timestamps no
                # longer line up with the frame indexes they would be read by.
                return None
            try:
                values.append(float(text))
            except ValueError:
                return None
        if not values:
            return None
        return _trusted_timeline(values, duration)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def probe_video_size(video_path: str, ffprobe: str | None = None) -> tuple[int, int] | None:
    """Return the source video's (width, height) in pixels via FFprobe.

    Returns None if FFprobe is unavailable, the probe fails, or the values
    cannot be parsed. Callers must treat None as "unknown" and fall back to a
    sensible aspect-ratio default.
    """
    ffprobe = ffprobe or shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0:s=x",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # As in probe_media_duration: a failed probe's output is not evidence,
        # even when it happens to be parsable. A wrong source size would feed
        # a wrong aspect ratio into the terminal grid calculation.
        if result.returncode != 0:
            return None
        text = result.stdout.decode(errors="replace").strip()
        if not text or "x" not in text:
            return None
        w, h = text.split("x", 1)
        width = int(w)
        height = int(h)
        if width <= 0 or height <= 0:
            return None
        return width, height
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
