"""Tests for the FFmpeg frame reader's partial-read and failure handling.

The real FFmpeg subprocess is exercised only by the one test at the bottom of
this file, which is skipped when FFmpeg is not installed; everything above it
verifies the exact-read loop against a fake byte stream that returns partial
chunks and drives the process lifecycle with a scripted fake Popen. That is
what proves a failed decode is reported as an error instead of a clean end of
playback, and that a merely-concealed corruption still plays through.
"""

import io
import re
import shutil
import subprocess
from unittest import mock

import pytest

from src.video import (
    FFmpegDecodeError,
    FFmpegFrameReader,
    FFmpegNotFoundError,
    classify_decode_termination,
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
    # -xerror must stay out: it made FFmpeg abort on a corruption the decoder
    # conceals and recovers from, killing playback that would otherwise be
    # fine. read_frame() now judges a clean exit by the captured log instead.
    assert "-xerror" not in cmd


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


def test_open_twice_terminates_the_first_process(tmp_path, monkeypatch):
    """A second open() must not orphan the first FFmpeg process.

    Without the guard, the first process keeps running with its stdout pipe
    and log file open but out of reach of close(), so it is never reaped.
    """
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    first = FakeFFmpegProc(alive=True)
    second = FakeFFmpegProc(alive=True)

    calls = iter([first, second])

    def _popen(cmd, **kwargs):
        return next(calls).attach(kwargs["stderr"])

    monkeypatch.setattr("src.video.subprocess.Popen", _popen)
    reader = FFmpegFrameReader(str(video), 4, 4, ffmpeg="ffmpeg")
    reader.open()
    reader.open()

    assert first.terminated == 1
    assert first.reaped >= 1
    assert first.stdout.closed
    assert first.stderr_file.closed
    assert reader._process is second
    reader.close()
    assert second.terminated == 1


# ---------------------------------------------------------------------------
# Decode strictness: what a short read on a clean exit actually means
# ---------------------------------------------------------------------------

# Real ffmpeg 9 output at "-loglevel error" *without* -xerror for the two
# canonical cases, shaped like _stderr_tail() hands it over (no trailing
# newline, most-recent lines last). A truncated download logs the fatal
# "partial file" marker inside a burst of decoder noise; a one-byte corruption
# logs only recoverable frame errors and still decodes every frame.
TRUNCATED_TAIL = (
    "[h264 @ 0000029f1c3b45a20] Reference 4 >= 4\n"
    "[h264 @ 0000029f1c3b45a20] error while decoding MB 13 0, bytestream 1409\n"
    "[h264 @ 0000029f1c3b45a20] Invalid NAL unit size (2851 > 1024), skipping 0 bytes\n"
    "[in#0/mov,mp4,m4a,3gp,3g2,mj2 @ 000001d663442480] stream 0, offset 0x12f87: partial file\n"
    "[h264 @ 0000029f1c3b45a20] missing picture in access unit"
)
CORRUPT_BYTE_TAIL = (
    "[h264 @ 0000029f1c3b45a20] Reference 5 >= 5\n"
    "[h264 @ 0000029f1c3b45a20] error while decoding MB 13 0, bytestream 1409"
)
CONCEALED_TAIL = (
    "[h264 @ 0000029f1c3b45a20] top block unavailable for requested intra4x4 mode\n"
    "[h264 @ 0000029f1c3b45a20] no frame! - increasing mb_size 32\n"
    "[h264 @ 0000029f1c3b45a20] mmco: unref short failure\n"
    "[h264 @ 0000029f1c3b45a20] co located POCs unavailable"
)


@pytest.mark.parametrize(
    "tail, fatal, marker",
    [
        # --- fatal: the container/stream itself ended early ----------------
        ("[mp4 @ 000001f4a1b2c3d0] moov atom not found", True, "moov atom not found"),
        ("[h264 @ 0000029f1c3b45a20] stream 0, offset 0x12f87: partial file",
         True, "partial file"),
        ("[in#0 @ 000001f4a1b2c3d0] Error opening input: Invalid data found "
         "when processing input", True, "error opening input"),
        # "corrupt input packet in stream %d" is what ffmpeg_demux.c logs for
        # AV_PKT_FLAG_CORRUPT -- at WARNING, and only fatal under -xerror
        # (which this reader no longer passes). Tolerated, not fatal.
        ("[error @ 0000029f1c3b45a20] corrupt input packet in stream 0: "
         "packet corrupt -845380487", False, None),
        # A truncated download: decoder noise, then the fatal marker inside it.
        # marker=None because the design does not fix WHICH of the fatal
        # markers a multi-marker tail reports -- only that it reports one.
        (TRUNCATED_TAIL, True, None),
        # --- benign: corruption the decoder concealed and recovered from ----
        ("[h264 @ 0000029f1c3b45a20] error while decoding MB 16 10, "
         "bytestream 376", False, None),
        ("[h264 @ 0000029f1c3b45a20] left block unavailable for requested "
         "intra4x4 mode", False, None),
        ("[h264 @ 0000029f1c3b45a20] Reference 3 >= 2", False, None),
        (CONCEALED_TAIL, False, None),
        (CORRUPT_BYTE_TAIL, False, None),
        # FFmpeg's generic summary lines, alone, say nothing about the cause.
        # ("Invalid NAL unit size" and "Invalid data found" both appear in
        # files that decode to the end) -- they must not condemn a file.
        ("[h264 @ 0000029f1c3b45a20] Invalid NAL unit size (2851 > 1024)", False, None),
        ("[error @ 000001f4a1b2c3d0] Invalid data found when processing input",
         False, None),
        ("[mp4 @ 000001f4a1b2c3d0] Error splitting the input into NAL units.",
         False, None),
        # --- case-insensitive matching (see the note below) ----------------
        ("[mp4 @ 000001f4a1b2c3d0] moov atom NOT found", True, "moov atom not found"),
        ("[h264 @ 0000029f1c3b45a20] stream 0, offset 0x0: PARTIAL FILE", True,
         "partial file"),
        # --- nothing to go on ----------------------------------------------
        ("", False, None),
        ("   \n\t\n  ", False, None),
    ],
)
def test_classify_decode_termination(tail, fatal, marker):
    reason = classify_decode_termination(tail)
    if not fatal:
        assert reason is None, f"benign decode noise misread as fatal: {reason!r}"
        return
    assert isinstance(reason, str) and reason.strip(), (
        "a fatal container error must produce a reason"
    )
    if marker is not None:
        assert marker in reason, f"reason does not name the marker: {reason!r}"


# ---------------------------------------------------------------------------
# Short read on a clean exit is decided by the captured log
# ---------------------------------------------------------------------------


def test_short_read_with_fatal_stderr_raises(tmp_path, monkeypatch):
    """exit 0 alone is not clean: a container error in the log is fatal.

    Without -xerror FFmpeg reports a truncated file and still exits 0, so the
    exit status on its own would have turned a half-downloaded clip into a
    normal end of playback. The captured log is the only evidence left.
    """
    reader, _proc = _reader(
        tmp_path,
        monkeypatch,
        stdout_bytes=b"\x01\x02",
        returncode=0,
        stderr_text=TRUNCATED_TAIL.encode(),
    )
    reason = classify_decode_termination(TRUNCATED_TAIL)
    with pytest.raises(FFmpegDecodeError) as excinfo:
        reader.read_frame()
    message = str(excinfo.value)
    assert reason in message, "the message must name why the stream really ended"
    assert not re.search(r"exit status [1-9]\d*", message), (
        f"FFmpeg exited 0 here, so the message must not claim a status: {message}"
    )
    reader.close()


def test_a_fatal_marker_outside_the_log_tail_is_still_fatal(tmp_path, monkeypatch):
    """Classification reads the WHOLE log, not just the 5-line tail.

    A truncated download logs a burst of decoder noise after the fatal marker;
    the marker must still be found even when it falls outside the tail that the
    error message quotes.
    """
    noise = b"".join(
        b"[h264 @ 0x1] error while decoding MB %d 0\n" % i for i in range(20)
    )
    reader, _proc = _reader(
        tmp_path, monkeypatch, stdout_bytes=b"\x01\x02", returncode=0,
        stderr_text=b"[mp4 @ 0x1] moov atom not found\n" + noise,
    )
    with pytest.raises(FFmpegDecodeError) as excinfo:
        reader.read_frame()
    assert "moov atom not found" in str(excinfo.value)
    reader.close()


def test_short_read_with_concealed_corruption_is_clean_eof(tmp_path, monkeypatch):
    """One flipped byte is concealment, not a container failure: keep playing.

    This is the case -xerror used to break: the decoder logs a decode error,
    recovers from it, still emits every frame and exits 0.
    """
    reader, _proc = _reader(
        tmp_path,
        monkeypatch,
        stdout_bytes=FRAME + b"\x01",
        returncode=0,
        stderr_text=CORRUPT_BYTE_TAIL.encode(),
    )
    assert reader.read_frame() == FRAME
    assert reader.read_frame() is None
    reader.close()


def test_short_read_with_nonzero_exit_reports_the_status_first(tmp_path, monkeypatch):
    """A non-zero exit outranks classification: the status is still the story."""
    reader, _proc = _reader(
        tmp_path,
        monkeypatch,
        stdout_bytes=b"\x01\x02",
        returncode=7,
        stderr_text=TRUNCATED_TAIL.encode(),
    )
    with pytest.raises(FFmpegDecodeError) as excinfo:
        reader.read_frame()
    message = str(excinfo.value)
    assert "exit status 7" in message
    assert "Invalid NAL unit size" in message  # FFmpeg's own log is still quoted
    reader.close()


def test_full_frames_are_returned_even_with_fatal_markers_logged(tmp_path, monkeypatch):
    """Classification runs on the outcome, never mid-stream.

    FFmpeg may have logged a container error for a file it is nonetheless
    still decoding; a fatal marker in the log must not cut playback short
    while whole frames keep arriving.
    """
    reader, _proc = _reader(
        tmp_path,
        monkeypatch,
        stdout_bytes=FRAME * 2,
        returncode=0,
        stderr_text=TRUNCATED_TAIL.encode(),
    )
    assert reader.read_frame() == FRAME
    assert reader.read_frame() == FRAME
    reader.close()  # no third read: that short read IS classified, and is fatal


def test_short_read_after_a_wait_timeout_is_classified(tmp_path, monkeypatch):
    """A decode still running when the pipe closes is decided by the log.

    wait() timing out is not a status, so this is the path a stalled or very
    slow truncated download actually takes -- it must not slip through as EOF.
    """
    reader, _proc = _reader(
        tmp_path,
        monkeypatch,
        stdout_bytes=b"\x01\x02",
        returncode=0,
        hang=True,
        stderr_text=TRUNCATED_TAIL.encode(),
    )
    with pytest.raises(FFmpegDecodeError) as excinfo:
        reader.read_frame()
    assert classify_decode_termination(TRUNCATED_TAIL) in str(excinfo.value)
    reader.close()


def test_short_read_after_a_wait_timeout_with_benign_log_is_eof(tmp_path, monkeypatch):
    """The timeout path stays a clean EOF when the log is only decoder noise."""
    reader, _proc = _reader(
        tmp_path,
        monkeypatch,
        stdout_bytes=b"\x01\x02",
        returncode=0,
        hang=True,
        stderr_text=CORRUPT_BYTE_TAIL.encode(),
    )
    assert reader.read_frame() is None
    reader.close()


def test_stderr_sink_failure_raises_decode_error(tmp_path, monkeypatch):
    """The stderr sink is now created inside the same try as the spawn.

    Its own failure must be reported like any other, not come out of the
    handler as an UnboundLocalError from closing a file that was never made.
    """
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")

    def _no_sink():
        raise OSError(145, "There is not enough space on the disk.")

    monkeypatch.setattr("src.video.tempfile.TemporaryFile", _no_sink)
    reader = FFmpegFrameReader(str(video), 4, 4, ffmpeg="ffmpeg")
    with pytest.raises(FFmpegDecodeError) as excinfo:
        reader.open()
    assert "not enough space" in str(excinfo.value)
    reader.close()


# ---------------------------------------------------------------------------
# The one test that shells out to a real FFmpeg (skipped when absent)
# ---------------------------------------------------------------------------

FFMPEG = shutil.which("ffmpeg")


def _make_clip(path, ffmpeg):
    """Write a 10-frame clip with FFmpeg's own built-in test source."""
    try:
        subprocess.run(
            [ffmpeg, "-v", "error", "-y",
             "-f", "lavfi", "-i", "testsrc=size=32x32:rate=10:duration=1",
             "-c:v", "mpeg4", str(path)],  # mpeg4: built into every build
            check=True, capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"this FFmpeg build cannot encode the test clip: {exc}")


def _decode_all(path, ffmpeg, width=16, height=16):
    """Drain a reader to EOF, returning the frames it produced."""
    reader = FFmpegFrameReader(str(path), width, height, ffmpeg=ffmpeg)
    frames = []
    reader.open()
    try:
        for _ in range(300):  # bounded: a reader that never reports EOF must
            frame = reader.read_frame()  # not hang the suite
            if frame is None:
                return frames
            frames.append(frame)
    finally:
        reader.close()
    raise AssertionError("the reader never reported end of stream")


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg is not installed")
def test_one_flipped_payload_byte_still_plays_every_frame(tmp_path):
    """A file with one corrupt byte must still play through.

    This is the whole point of dropping -xerror: on this machine -xerror makes
    FFmpeg quit after 4 of 10 frames with a non-zero status, while without it
    FFmpeg conceals the damage, emits all 10 and exits 0 -- so neither the
    exit status nor the log may be allowed to call that a failed decode.
    """
    clean = tmp_path / "clean.mp4"
    _make_clip(clean, FFMPEG)

    data = bytearray(clean.read_bytes())
    box = data.find(b"mdat")
    if box < 0:
        pytest.skip("no mdat box in the generated clip")
    # A box is [4-byte size][4-byte type][payload]; find() returns the TYPE
    # field, so the size sits four bytes earlier and the payload starts four
    # bytes later. Assuming the payload runs to EOF is invalid because with a
    # default (non-faststart) layout the moov box follows mdat -- read the size
    # field so the flip lands inside the mdat payload, not in moov.
    size = int.from_bytes(data[box - 4:box], "big")
    if size <= 8 or box - 4 + size > len(data):
        pytest.skip("unexpected mdat box layout in the generated clip")
    data[box + 4 + (size - 8) // 2] ^= 0xFF
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(bytes(data))

    intact = _decode_all(clean, FFMPEG)
    assert len(intact) == 10, "the clip did not decode; this test proves nothing"

    # Must not raise: a raise here IS the regression -xerror reintroduced.
    frames = _decode_all(corrupt, FFMPEG)
    assert frames and all(len(f) == 16 * 16 * 3 for f in frames)
    # Concealment can cost a frame on some builds, so allow one; losing the
    # rest of the clip would mean the corruption actually truncated it.
    assert len(frames) >= len(intact) - 1
