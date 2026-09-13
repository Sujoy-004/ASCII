"""Audio playback via FFplay and audio-stream detection via FFprobe.

Launches FFplay as a separate process to play audio directly to the speakers,
independent of the video rendering pipeline. Process management and the
reliable detection of whether a video even contains an audio stream live here.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
import time

from src.sync import AudioStatus


class FFplayNotFoundError(RuntimeError):
    """Raised when FFplay is requested but cannot be located."""


_STATS_RE = re.compile(
    rb"\s*(-?\d+(?:\.\d+)?)\s+(?:A-V|M-A|M-V|\s*):\s*(-?\d+(?:\.\d+)?)"
)


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
        self._stats_thread: threading.Thread | None = None
        self._stats_stop = threading.Event()
        self._stats_ready = threading.Event()
        self._stats_lock = threading.Lock()
        self._media_position: float | None = None
        self._media_position_at: float | None = None
        self._sync_drift: float | None = None
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
        cmd = [
            self.ffplay,
            "-vn",
            "-nodisp",
            "-autoexit",
            "-stats",
            "-loglevel", "warning",
            video_path,
        ]
        self.launched_at = self._now()
        self.exit_at = None
        self._stats_stop.clear()
        self._stats_ready.clear()
        with self._stats_lock:
            self._media_position = None
            self._media_position_at = None
            self._sync_drift = None
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        stderr = getattr(self._process, "stderr", None)
        if stderr is not None:
            self._stats_thread = threading.Thread(
                target=self._read_stats,
                args=(stderr,),
                name="ffplay-stats",
                daemon=True,
            )
            self._stats_thread.start()
        else:
            self._stats_thread = None

    def _read_stats(self, stderr) -> None:
        """Read FFplay status lines and retain its audio-master media clock.

        FFplay emits carriage-return-delimited status containing its master
        clock and drift. With audio-only playback the master clock is the
        audio clock by default, so the first numeric field is the best
        externally observable media-position estimate available through this
        subprocess architecture.
        """
        pending = b""
        read1 = getattr(stderr, "read1", stderr.read)
        try:
            while not self._stats_stop.is_set():
                chunk = read1(4096)
                if not chunk:
                    break
                pending += chunk
                parts = re.split(rb"[\r\n]", pending)
                pending = parts.pop()
                for part in parts:
                    match = _STATS_RE.search(part)
                    if match is None:
                        continue
                    try:
                        position = float(match.group(1))
                        drift = float(match.group(2))
                    except ValueError:
                        continue
                    observed_at = self._now()
                    with self._stats_lock:
                        self._media_position = position
                        self._media_position_at = observed_at
                        self._sync_drift = drift
                    self._stats_ready.set()
        except (OSError, ValueError):
            return

    def wait_for_media_clock(self, timeout: float = 0.25) -> bool:
        """Wait briefly for the first FFplay media-position observation."""
        return self._stats_ready.wait(max(0.0, timeout))

    @property
    def sync_drift(self) -> float | None:
        """Latest FFplay-reported master/audio drift, when available."""
        with self._stats_lock:
            return self._sync_drift

    def media_position(self) -> float | None:
        """Estimate current audio media time from FFplay's status clock.

        The reported position is anchored at the time this process observes
        FFplay's status line, then extrapolated at 1x while FFplay remains
        running. This is an audio-derived media clock, not an audio-device
        sample timestamp.
        """
        with self._stats_lock:
            position = self._media_position
            observed_at = self._media_position_at
        if position is None or observed_at is None:
            return None
        process = self._process
        if process is not None:
            try:
                running = process.poll() is None
            except OSError:
                running = False
            if running:
                return max(position, position + max(0.0, self._now() - observed_at))
        return position

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
        self._stats_stop.set()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        thread = self._stats_thread
        self._stats_thread = None
        if thread is not None:
            thread.join(timeout=0.5)
        stderr = getattr(proc, "stderr", None)
        if stderr is not None:
            try:
                stderr.close()
            except OSError:
                pass
