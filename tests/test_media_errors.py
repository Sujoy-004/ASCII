"""End-to-end tests: a media failure must never exit 0.

The reader-level tests in test_frame_reader.py prove the FFmpeg process is
inspected; these prove the failure survives all the way to the process exit
code, and that cleanup still happens on the way out. Everything is faked --
no real terminal, no real FFmpeg.
"""

import io
from unittest import mock

import pytest

from src.audio import AudioPlayer
from src.config import Config
from src.main import main, run
from src.renderer import RGBAsciiRenderer
from src.sync import AudioStatus, PlaybackTimeline
from src.timing import FrameClock

FRAME = bytes(2 * 2 * 3)  # one frame at the 2x2 reader size below


class FakeFFmpegProc:
    """Fake FFmpeg Popen result: scripted stdout, a fixed exit status."""

    def __init__(self, stdout_bytes=b"", returncode=0, stderr_text=b""):
        self.stdout = io.BytesIO(stdout_bytes)
        self.returncode = returncode
        self.stderr_text = stderr_text
        self.stderr_file = None
        self.terminated = 0
        self.killed = 0

    def attach(self, stderr_file):
        self.stderr_file = stderr_file
        stderr_file.write(self.stderr_text)
        return self

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated += 1

    def kill(self):
        self.killed += 1

    @property
    def stdout_closed(self):
        return self.stdout.closed

    @property
    def stderr_closed(self):
        return self.stderr_file is not None and self.stderr_file.closed


class FakeTerminal:
    """Terminal stand-in that records what the loop did to it."""

    def __init__(self, _config=None, size=(2, 2)):
        self.width, self.height = 40, 12
        self._size = size
        self.written = 0
        self.restored = 0
        self.cleared = 0

    def init(self):
        pass

    def output_size(self, _video_aspect=None):
        return self._size

    def refresh_size(self):
        return False

    def write_frame(self, _frame_string):
        self.written += 1

    def clear(self):
        self.cleared += 1

    def restore(self):
        self.restored += 1


def _noop_sleep(_seconds):
    pass


def _run_with(tmp_path, monkeypatch, *, stdout_bytes, returncode, stderr_text=b""):
    """Run the real main() against a fake FFmpeg process and a fake terminal."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not really a video")
    proc = FakeFFmpegProc(stdout_bytes, returncode, stderr_text)

    monkeypatch.setattr("src.video.subprocess.Popen", lambda cmd, **kw: proc.attach(kw["stderr"]))
    # The decoder resolves ffmpeg by name before spawning it; point that at a
    # path so the test does not need a real FFmpeg installed.
    monkeypatch.setattr("src.video.shutil.which", lambda name: name)
    monkeypatch.setattr("src.main.TerminalRenderer", FakeTerminal)
    monkeypatch.setattr("src.main.probe_media_duration", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_size", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_timestamps", lambda *a, **k: None)
    monkeypatch.setenv("RGB_ASCII_NO_AUDIO", "1")  # keep the CLI path audio-free
    monkeypatch.setenv("RGB_ASCII_FPS", "1000")
    return proc, main([str(video)])


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

def test_invalid_video_exits_non_zero(tmp_path, monkeypatch):
    """A decoder failure must not look like successful playback."""
    _proc, code = _run_with(
        tmp_path,
        monkeypatch,
        stdout_bytes=b"",
        returncode=1,
        stderr_text=b"clip.mp4: Invalid data found when processing input\n",
    )
    assert code == 1


def test_invalid_video_reports_error_without_traceback(tmp_path, monkeypatch, capsys):
    """CLI users get a readable message, not a Python traceback."""
    _run_with(
        tmp_path,
        monkeypatch,
        stdout_bytes=b"",
        returncode=1,
        stderr_text=b"Invalid data found when processing input\n",
    )
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "exit status 1" in err
    assert "Invalid data found when processing input" in err


def test_valid_video_still_exits_zero(tmp_path, monkeypatch):
    """The normal path must be completely unaffected by the added checks."""
    proc, code = _run_with(
        tmp_path, monkeypatch, stdout_bytes=FRAME * 2, returncode=0
    )
    assert code == 0
    assert proc.stdout_closed
    assert proc.stderr_closed


# ---------------------------------------------------------------------------
# Cleanup on failure
# ---------------------------------------------------------------------------

def test_failure_closes_ffmpeg_resources(tmp_path, monkeypatch):
    """The reader is closed on the way out even when the loop raised."""
    proc, _code = _run_with(
        tmp_path, monkeypatch, stdout_bytes=b"", returncode=1
    )
    assert proc.stdout_closed, "stdout pipe leaked on the failure path"
    assert proc.stderr_closed, "captured stderr leaked on the failure path"


def test_failure_does_not_leave_ffplay_running():
    """A decoder failure stops audio immediately rather than draining it.

    On failure the reader raises, so the loop's normal_eof path (which waits
    for FFplay to finish) must not engage -- a failed decode should not play
    out the rest of the audio track.
    """

    class FakeProc:
        def __init__(self):
            self._exited = False
            self.terminated = 0
            self.stderr = io.BytesIO(b"")

        def poll(self):
            return 0 if self._exited else None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            self.terminated += 1
            self._exited = True

        def kill(self):
            self._exited = True

    class FailingReader:
        """A reader that dies mid-stream the way FFmpeg failure now does."""

        width = height = 2

        def __init__(self):
            self.closed = False

        def read_frame(self):
            raise RuntimeError("decoder died")

        def close(self):
            self.closed = True

    ffplay = FakeProc()
    reader = FailingReader()
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=1000)
    timeline = PlaybackTimeline(
        playback_start=0.0, audio_status=AudioStatus.CONFIRMED, audio_launched_at=0.0
    )
    audio = AudioPlayer(ffplay="ffplay")

    with mock.patch("src.audio.subprocess.Popen", return_value=ffplay), \
            pytest.raises(RuntimeError):
        run(
            reader, RGBAsciiRenderer(config), terminal,
            FrameClock(1000, sleep_fn=_noop_sleep), config, audio, timeline,
            media_duration=None,
        )

    assert reader.closed, "FFmpeg reader not closed on the error path"
    assert terminal.restored >= 1, "terminal not restored on the error path"
    assert audio._process is None, "FFplay left running on the error path"
    assert timeline.audio_waited_for_exit is False, (
        "should not wait for natural audio exit on a decoder failure"
    )
