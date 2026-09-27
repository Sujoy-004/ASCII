"""Tests for the FFmpeg frame reader's partial-read and failure handling.

The real FFmpeg subprocess is not exercised here (it would be slow and
environment-dependent). Instead we verify the exact-read loop against a fake
byte stream that returns partial chunks, and drive the process lifecycle with a
scripted fake Popen -- which is what proves a failed decode is reported as an
error instead of a clean end of playback.
"""

import io
import subprocess
from unittest import mock

import pytest

from src.video import (
    FFmpegDecodeError,
    FFmpegFrameReader,
    FFmpegNotFoundError,
)


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


def test_decode_command_preserves_variable_frame_rate(tmp_path, monkeypatch):
    """The decode pipe must emit exactly one frame per source frame.

    Without -fps_mode passthrough, FFmpeg resamples the rawvideo output to a
    constant frame rate, duplicating frames to fill a variable-rate source's
    gaps. Those duplicates land between the real frames, so the pipe's frame
    index stops matching the probed source PTS list and every frame after a
    gap gets another frame's deadline.
    """
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not really a video")
    captured = {}

    def _popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeFFmpegProc().attach(kwargs["stderr"])

    monkeypatch.setattr("src.video.subprocess.Popen", _popen)
    reader = FFmpegFrameReader(str(video), 4, 4, ffmpeg="ffmpeg")
    reader.open()
    reader.close()
    cmd = captured["cmd"]
    assert cmd[cmd.index("-fps_mode") + 1] == "passthrough"
    assert "-xerror" in cmd  # the prior hardening must survive


# ---------------------------------------------------------------------------
# Process lifecycle: a failed decode must never look like a clean EOF
# ---------------------------------------------------------------------------

FRAME = bytes(4 * 4 * 3)  # one frame at the 4x4 reader size below


class FakeFFmpegProc:
    """Stand-in for the FFmpeg Popen result with a scripted outcome."""

    def __init__(self, stdout_bytes=b"", returncode=0, stderr_text=b"",
                 alive=False, hang=False, terminate_raises=False):
        self.stdout = io.BytesIO(stdout_bytes)
        self.returncode = returncode
        self.alive = alive
        self.hang = hang
        self.terminate_raises = terminate_raises
        self.stderr_file = None
        self.stderr_text = stderr_text
        self.terminated = 0
        self.killed = 0
        self.reaped = 0

    def attach(self, stderr_file):
        """Receive the real stderr sink and record what FFmpeg 'logged'."""
        self.stderr_file = stderr_file
        stderr_file.write(self.stderr_text)
        return self

    def poll(self):
        return None if self.alive else self.returncode

    def wait(self, timeout=None):
        self.reaped += 1
        if self.hang:
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=timeout)
        self.alive = False
        return self.returncode

    def terminate(self):
        self.terminated += 1
        if self.terminate_raises:
            raise OSError(5, "Access is denied")
        self.alive = False

    def kill(self):
        self.killed += 1
        self.alive = False


def _reader(tmp_path, monkeypatch, **proc_kwargs):
    """Return (reader, proc) wired to a scripted fake FFmpeg process."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not really a video")
    proc = FakeFFmpegProc(**proc_kwargs)

    def _popen(cmd, **kwargs):
        return proc.attach(kwargs["stderr"])

    monkeypatch.setattr("src.video.subprocess.Popen", _popen)
    reader = FFmpegFrameReader(str(video), 4, 4, ffmpeg="ffmpeg")
    reader.open()
    return reader, proc


def test_normal_eof_after_frames_still_succeeds(tmp_path, monkeypatch):
    """A clean run must be unaffected: full frames, then a plain None at EOF."""
    reader, proc = _reader(
        tmp_path, monkeypatch, stdout_bytes=FRAME * 2, returncode=0
    )
    assert reader.read_frame() == FRAME
    assert reader.read_frame() == FRAME
    assert reader.read_frame() is None
    reader.close()
    assert proc.terminated == 0  # already gone, nothing to kill


def test_nonzero_exit_with_no_output_raises(tmp_path, monkeypatch):
    """Corrupt input: FFmpeg exits non-zero before any frame -> hard error."""
    reader, _proc = _reader(
        tmp_path,
        monkeypatch,
        returncode=1,
        stderr_text=b"clip.mp4: Invalid data found when processing input\n",
    )
    with pytest.raises(FFmpegDecodeError) as excinfo:
        reader.read_frame()
    message = str(excinfo.value)
    assert "exit status 1" in message
    assert "Invalid data found when processing input" in message
    reader.close()


def test_nonzero_exit_mid_stream_raises(tmp_path, monkeypatch):
    """Frames already delivered do not make a mid-stream failure a success."""
    reader, _proc = _reader(
        tmp_path,
        monkeypatch,
        stdout_bytes=FRAME + b"\x01",
        returncode=234,
        stderr_text=b"[error] corrupted frame\n",
    )
    assert reader.read_frame() == FRAME
    with pytest.raises(FFmpegDecodeError) as excinfo:
        reader.read_frame()
    assert "exit status 234" in str(excinfo.value)
    reader.close()


def test_partial_frame_with_nonzero_exit_raises(tmp_path, monkeypatch):
    """A truncated final frame is a failure, not a short frame to render."""
    reader, _proc = _reader(
        tmp_path, monkeypatch, stdout_bytes=FRAME + b"\x01\x02", returncode=1
    )
    assert reader.read_frame() == FRAME
    with pytest.raises(FFmpegDecodeError):
        reader.read_frame()
    reader.close()


def test_partial_frame_with_clean_exit_is_eof(tmp_path, monkeypatch):
    """A truncated frame from a clean exit ends playback instead of crashing."""
    reader, _proc = _reader(
        tmp_path, monkeypatch, stdout_bytes=b"\x01\x02", returncode=0
    )
    assert reader.read_frame() is None
    reader.close()


def test_pipe_eof_while_process_still_running_is_eof(tmp_path, monkeypatch):
    """stdout closed but the child has not been reaped yet: no error, no hang."""
    reader, _proc = _reader(
        tmp_path, monkeypatch, stdout_bytes=b"", returncode=0, hang=True
    )
    assert reader.read_frame() is None
    reader.close()


def test_startup_failure_raises_decode_error(tmp_path, monkeypatch):
    """A broken/missing FFmpeg binary must surface as an error, not a traceback."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    stderr = io.BytesIO()
    monkeypatch.setattr("src.video.tempfile.TemporaryFile", lambda: stderr)

    def _boom(_cmd, **_kwargs):
        raise OSError(193, "%1 is not a valid Win32 application")

    monkeypatch.setattr("src.video.subprocess.Popen", _boom)
    reader = FFmpegFrameReader(str(video), 4, 4, ffmpeg="ffmpeg")
    with pytest.raises(FFmpegDecodeError) as excinfo:
        reader.open()
    message = str(excinfo.value)
    assert "could not be started" in message
    assert "not a valid Win32 application" in message
    assert stderr.closed  # the stderr sink is not leaked on startup failure
    reader.close()       # and closing a reader that never opened is safe


def test_open_captures_ffmpeg_diagnostics(tmp_path, monkeypatch):
    """FFmpeg's log must be kept (not thrown away) so errors can be explained."""
    reader, _proc = _reader(tmp_path, monkeypatch, stderr_text=b"a logged line\n")
    assert reader._stderr_tail() == "a logged line"
    reader.close()


def test_close_terminates_reaps_and_closes_streams(tmp_path, monkeypatch):
    reader, proc = _reader(tmp_path, monkeypatch, alive=True)
    reader.close()
    assert proc.terminated == 1
    assert proc.reaped >= 1        # reaped, so no zombie is left behind
    assert proc.stdout.closed      # stdout released
    assert proc.stderr_file.closed  # captured log released
    reader.close()                 # idempotent
    assert proc.terminated == 1


def test_close_kills_process_that_ignores_terminate(tmp_path, monkeypatch):
    reader, proc = _reader(tmp_path, monkeypatch, alive=True, hang=True)
    reader.close()
    assert proc.terminated == 1
    assert proc.killed == 1
    assert proc.reaped >= 2  # wait after terminate times out, then best-effort reaping
    assert proc.stdout.closed


def test_close_survives_terminate_error(tmp_path, monkeypatch):
    """Cleanup runs from finally blocks, so it must never raise or skip streams."""
    reader, proc = _reader(
        tmp_path, monkeypatch, alive=True, terminate_raises=True
    )
    reader.close()
    assert proc.stdout.closed
    assert proc.stderr_file.closed
