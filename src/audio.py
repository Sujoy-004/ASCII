"""Audio playback via FFplay and audio-stream detection via FFprobe.

Launches FFplay as a separate process to play audio directly to the speakers,
independent of the video rendering pipeline. Process management and the
reliable detection of whether a video even contains an audio stream live here.
"""

from __future__ import annotations

import shutil
import subprocess
import time

from src.sync import AudioStatus


class FFplayNotFoundError(RuntimeError):
    """Raised when FFplay is requested but cannot be located."""


def _probe_ffprobe(video_path: str, ffprobe: str | None) -> AudioStatus:
    """Probe for an audio stream, returning a tri-state result."""
    ffprobe = ffprobe or shutil.which("ffprobe")
    if ffprobe is None:
        return AudioStatus.UNKNOWN
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return AudioStatus.CONFIRMED if result.stdout else AudioStatus.ABSENT
    except (OSError, subprocess.SubprocessError):
        return AudioStatus.UNKNOWN


def detect_audio_status(
    video_path: str, ffprobe: str | None = None
) -> AudioStatus:
    """Return CONFIRMED / ABSENT / UNKNOWN for the video's audio stream.

    - CONFIRMED: ffprobe positively found >=1 audio stream.
    - ABSENT:    ffprobe positively found no audio stream.
    - UNKNOWN:   ffprobe is unavailable or the probe failed; we cannot know,
                 so callers who want audible output should attempt FFplay.
    """
    return _probe_ffprobe(video_path, ffprobe)


def has_audio_stream(video_path: str, ffprobe: str | None = None) -> bool:
    """Backward-compatible boolean: True unless audio is confirmed absent.

    Kept for callers that only need a yes/no; new code should use
    ``detect_audio_status`` so CONFIRMED and UNKNOWN are distinguishable.
    """
    return detect_audio_status(video_path, ffprobe) is not AudioStatus.ABSENT


class AudioPlayer:
    """Manages the FFplay audio subprocess and records its timing.

    ``launched_at`` / ``exit_at`` are monotonic timestamps on the same clock
    as the shared playback timeline. ``now`` and ``sleep_fn`` are injectable
    so tests can measure lifecycle deterministically without real audio.
    """

    def __init__(
        self,
        ffplay: str | None = None,
        now=None,
        sleep_fn=None,
    ) -> None:
        self.ffplay = ffplay or shutil.which("ffplay")
        self._process: subprocess.Popen[bytes] | None = None
        self.launched_at: float | None = None
        self.exit_at: float | None = None
        self._now = now if now is not None else time.perf_counter
        self._sleep = sleep_fn if sleep_fn is not None else time.sleep

    def start(self, video_path: str) -> None:
        """Launch FFplay to play the video's audio without a video window.

        The video path is passed as a single argument (FFplay handles paths
        containing spaces correctly when passed as one argv element).
        """
        if self.ffplay is None:
            raise FFplayNotFoundError(
                "FFplay is required for audio but was not found. "
                "FFplay plays the video's audio track.\n"
                "  Install FFmpeg/FFplay from https://ffmpeg.org/download.html "
                "(Windows builds from https://www.gyan.dev/ffmpeg/builds/ include "
                "FFplay).\n"
                "  Add the folder containing ffplay.exe to your system PATH, then "
                "open a NEW terminal window.\n"
                "  To play video without audio, set the RGB_ASCII_NO_AUDIO=1 "
                "environment variable before running."
            )
        cmd = [self.ffplay, "-nodisp", "-autoexit", video_path]
        self.launched_at = self._now()
        self.exit_at = None
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def is_running(self) -> bool:
        """Return True if the FFplay process is currently alive.

        Records ``exit_at`` the first time the process is observed as exited.
        """
        if self._process is None:
            return False
        running = self._process.poll() is None
        if not running and self.exit_at is None:
            self.exit_at = self._now()
        return running

    def wait_for_exit(self, timeout: float) -> bool:
        """Wait up to ``timeout`` seconds for FFplay to exit naturally.

        Returns True if it exited on its own within the timeout, False
        otherwise (caller should then force a stop). Polling a live subprocess
        only; never blocks past the timeout.
        """
        if self._process is None:
            return True
        deadline = self._now() + timeout
        while self.is_running():
            if self._now() >= deadline:
                return False
            self._sleep(0.02)
        return True

    def stop(self) -> None:
        """Terminate the FFplay process if it is still running."""
        if self._process is None:
            return
        proc = self._process
        self._process = None
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
