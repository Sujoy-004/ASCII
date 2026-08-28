"""Playback synchronization: a shared master timeline and A/V timing model.

Keeps the three temporal notions the rest of the system must keep distinct:

- wall/process time  -- raw monotonic seconds (time.perf_counter)
- video presentation time -- driven by FrameClock absolute deadlines
- audio playback time -- driven by the external FFplay process

This module owns the single shared ``playback_start`` reference, the per
subsystem timing observations, audio-status tri-state, and the
end-of-playback completion policy. It does not launch processes or render
video.
"""

from __future__ import annotations

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
        text = result.stdout.decode(errors="replace").strip()
        if not text:
            return None
        return float(text)
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
