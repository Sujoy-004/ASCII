"""Tests for the FFmpeg frame reader's partial-read handling.

The real FFmpeg subprocess is not exercised here (it would be slow and
environment-dependent). Instead we verify the exact-read loop against a fake
byte stream that returns partial chunks, which is the part that matters.
"""

from unittest import mock

import pytest

from src.video import FFmpegFrameReader, FFmpegNotFoundError


class _ChunkedStream:
    """A fake stream whose read() returns short chunks to simulate a pipe."""

    def __init__(self, data: bytes, chunk: int) -> None:
        self.data = data
        self.chunk = chunk
        self.pos = 0

    def read(self, n: int) -> bytes:
        if self.pos >= len(self.data):
            return b""
        end = self.pos + self.chunk
        piece = self.data[self.pos:end]
        self.pos = end
        return piece


def test_read_exact_full():
    stream = _ChunkedStream(bytes(range(12)), 3)
    assert FFmpegFrameReader._read_exact(stream, 12) == bytes(range(12))


def test_read_exact_partial_chunks():
    stream = _ChunkedStream(bytes(range(12)), 5)  # uneven chunks
    assert FFmpegFrameReader._read_exact(stream, 12) == bytes(range(12))


def test_read_exact_eof_at_exact_boundary():
    stream = _ChunkedStream(bytes(range(12)), 6)
    assert FFmpegFrameReader._read_exact(stream, 12) == bytes(range(12))


def test_read_exact_eof_short():
    # Stream ends before the requested length: return partial data.
    stream = _ChunkedStream(b"abcd", 2)
    assert FFmpegFrameReader._read_exact(stream, 8) == b"abcd"


def test_read_exact_empty():
    stream = _ChunkedStream(b"", 4)
    assert FFmpegFrameReader._read_exact(stream, 12) == b""


def test_missing_ffmpeg_raises_with_clear_message():
    """FFmpeg is required; the error must say it is required and how to install."""
    with mock.patch("src.video.shutil.which", return_value=None):
        with pytest.raises(FFmpegNotFoundError) as excinfo:
            FFmpegFrameReader("clip.mp4", 10, 10, ffmpeg=None)
    msg = str(excinfo.value)
    assert "required" in msg
    assert "https://ffmpeg.org/download.html" in msg
    assert "PATH" in msg
    assert "ffmpeg -version" in msg
