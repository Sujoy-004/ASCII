"""FFmpeg-based video frame decoding.

Launches FFmpeg as a subprocess, requests raw RGB24 frames on stdout, and
exposes them as bytes. This module knows nothing about ANSI or terminals.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass


class FFmpegNotFoundError(RuntimeError):
    """Raised when the FFmpeg executable cannot be located."""


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
        self.launched_at: float | None = None
        self.media_timestamps: tuple[float, ...] | None = None

    def open(self) -> None:
        """Start the FFmpeg process producing RGB24 frames on stdout."""
        if not os.path.isfile(self.video_path):
            raise FileNotFoundError(f"Video not found: {self.video_path}")

        cmd = [
            self.ffmpeg,
            "-i", self.video_path,
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-vf", f"scale={self.width}:{self.height}",
            "-",
        ]
        # read frames from stdout as binary; ignore ffmpeg logging on stderr.
        self.launched_at = time.perf_counter()
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def read_frame(self) -> bytes | None:
        """Read exactly one frame, or None on EOF.

        Robustly handles partial reads from the pipe: loops until the full
        frame_size bytes are collected or the stream ends.
        """
        proc = self._process
        if proc is None or proc.stdout is None:
            return None
        data = self._read_exact(proc.stdout, self.frame_size)
        return data if data else None

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
        """Terminate the FFmpeg process safely."""
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
        if proc.stdout is not None:
            proc.stdout.close()

    def __enter__(self) -> "FFmpegFrameReader":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
