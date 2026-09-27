"""FFmpeg-based video frame decoding.

Launches FFmpeg as a subprocess, requests raw RGB24 frames on stdout, and
exposes them as bytes. This module knows nothing about ANSI or terminals.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Any


class FFmpegNotFoundError(RuntimeError):
    """Raised when the FFmpeg executable cannot be located."""


class FFmpegDecodeError(RuntimeError):
    """Raised when the FFmpeg decoder fails or exits with a non-zero status."""


@dataclass
class ScaleDim:
    """Output dimension for FFmpeg scaling (width x height)."""

    width: int
    height: int


def _find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path is None:
        raise FFmpegNotFoundError(
            "FFmpeg is required but was not found. "
            "FFmpeg decodes the video into ASCII frames and must be installed.\n"
            "  You can install FFmpeg from https://ffmpeg.org/download.html\n"
            "  (the Windows builds from https://www.gyan.dev/ffmpeg/builds/ also "
            "include FFplay).\n"
            "  Add the folder containing ffmpeg.exe and ffplay.exe to your system "
            "PATH, then open a NEW terminal window.\n"
            "  Verify with:  ffmpeg -version"
        )
    return path


class FFmpegFrameReader:
    """Reads RGB24 frames from an FFmpeg subprocess."""

    def __init__(
        self,
        video_path: str,
        width: int,
        height: int,
        fps: int = 30,
        ffmpeg: str | None = None,
    ) -> None:
        self.video_path = video_path
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_size = width * height * 3
        self.ffmpeg = ffmpeg or _find_ffmpeg()
        self._process: subprocess.Popen[bytes] | None = None
        # Platform-dependent wrapper; used only as a seekable byte sink.
        self._stderr_file: Any = None
        self.launched_at: float | None = None
        self.media_timestamps: tuple[float, ...] | None = None

    def open(self) -> None:
        """Start the FFmpeg process producing RGB24 frames on stdout."""
        if not os.path.isfile(self.video_path):
            raise FileNotFoundError(f"Video not found: {self.video_path}")

        cmd = [
            self.ffmpeg,
            # -xerror: FFmpeg otherwise logs a decode error and still exits 0
            # (e.g. a truncated file), which would hide a failed decode behind
            # a normal end of stream. With it, any decode error fails the
            # process so read_frame() can tell failure from EOF.
            "-xerror",
            "-i", self.video_path,
            # -fps_mode passthrough: without it FFmpeg resamples the output to a
            # constant frame rate, duplicating frames to fill a variable-rate
            # source's gaps. Those duplicates land between the real frames, so
            # the pipe's frame index stops matching the source PTS list probed
            # by src.sync and every frame after a gap gets the wrong deadline.
            # Passthrough keeps one pipe frame per source frame, which is what
            # makes frame index and presentation timestamp the same thing.
            # (Replaces -vsync 0, which FFmpeg 9 removed; needs FFmpeg 5+.)
            "-fps_mode", "passthrough",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            # flags=area = box/area-average scaling: each decoded pixel is the
            # mean of the entire source region it covers, so the color every
            # terminal character receives reflects its whole region rather than
            # one arbitrary pixel. Area averaging is also cheaper than the
            # default bicubic for large downscales, keeping real-time playback.
            "-vf", f"scale={self.width}:{self.height}:flags=area",
            "-loglevel", "error",
            "-",
        ]
        # FFmpeg's own diagnostics are what makes a decode failure explainable,
        # so keep them (errors only) in a temp file rather than a pipe: an
        # undrained pipe would eventually block FFmpeg mid-decode, while a temp
        # file grows freely and is read only once a failure needs explaining.
        stderr_file = tempfile.TemporaryFile()
        # read frames from stdout as binary.
        self.launched_at = time.perf_counter()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=stderr_file,
            )
        except OSError as exc:
            stderr_file.close()
            raise FFmpegDecodeError(
                f"FFmpeg could not be started: {exc}\n"
                f"  Verify the executable with:  {self.ffmpeg} -version"
            ) from exc
        self._stderr_file = stderr_file
        self._process = proc

    def read_frame(self) -> bytes | None:
        """Read exactly one frame, or None on a normal end of stream.

        Robustly handles partial reads from the pipe: loops until the full
        frame_size bytes are collected or the stream ends.

        A short read is a normal EOF only when FFmpeg itself exited cleanly. A
        non-zero exit is a decoder failure and raises FFmpegDecodeError, so a
        corrupt/unsupported input can never be reported as successful playback.
        """
        proc = self._process
        if proc is None or proc.stdout is None:
            return None
        data = self._read_exact(proc.stdout, self.frame_size)
        if len(data) == self.frame_size:
            return data
        # The pipe ended before a whole frame: either a clean end of stream or
        # FFmpeg dying mid-decode. Only the exit status tells the two apart.
        try:
            code = proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            code = 0  # stdout is closed, so no further frame can ever arrive
        if code != 0:
            raise FFmpegDecodeError(self._failure_message(code))
        return None

    def _failure_message(self, code: int) -> str:
        """Describe a decoder failure, quoting FFmpeg's own last log lines."""
        message = (
            f"FFmpeg failed to decode {self.video_path} (exit status {code})."
        )
        detail = self._stderr_tail()
        return f"{message}\nFFmpeg reported:\n{detail}" if detail else message

    def _stderr_tail(self, lines: int = 5) -> str:
        """Return the tail of FFmpeg's captured log, or '' if unavailable."""
        stream = self._stderr_file
        if stream is None:
            return ""
        try:
            stream.seek(0)
            text = stream.read().decode(errors="replace")
        except OSError:
            return ""
        return "\n".join(text.strip().splitlines()[-lines:])

    @staticmethod
    def _read_exact(stream, length: int) -> bytes:
        """Read exactly `length` bytes, tolerating short reads.

        Returns an empty bytes object if the stream yields nothing at all.
        If the stream ends partway, returns whatever was collected.
        """
        out = bytearray()
        while len(out) < length:
            chunk = stream.read(length - len(out))
            if not chunk:
                break
            out.extend(chunk)
        return bytes(out)

    def close(self) -> None:
        """Terminate the FFmpeg process and release its pipes.

        Never raises: this runs from ``finally`` blocks, and a failure here
        would otherwise skip the terminal restore and the audio cleanup.
        """
        proc, self._process = self._process, None
        stderr_file, self._stderr_file = self._stderr_file, None
        try:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass  # best effort reaping
        except OSError:
            pass
        finally:
            for stream in (getattr(proc, "stdout", None), stderr_file):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass

    def __enter__(self) -> "FFmpegFrameReader":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
