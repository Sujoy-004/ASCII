"""Tests for Milestone 4: FFplay audio playback and audio-stream detection.

No real audio is played or probed here; subprocess.Popen is mocked so the
command construction, lifecycle, and cleanup can be verified deterministically.
"""

import subprocess
from unittest import mock

import pytest

from src.audio import FFplayNotFoundError, AudioPlayer, has_audio_stream


class FakeProc:
    """Minimal stand-in for a subprocess.Popen result."""

    def __init__(self, exited=False):
        self._exited = exited
        self.terminated = 0
        self.killed = 0

    def poll(self):
        return None if not self._exited else 0

    def terminate(self):
        self.terminated += 1
        self._exited = True

    def kill(self):
        self.killed += 1
        self._exited = True

    def wait(self, timeout=None):
        return 0


@pytest.fixture
def fake_popen():
    state = {"calls": [], "proc": FakeProc()}

    def _popen(cmd, **kwargs):
        state["calls"].append((cmd, kwargs))
        return state["proc"]

    with mock.patch("src.audio.subprocess.Popen", side_effect=_popen):
        yield state


def test_start_command_construction(fake_popen):
    player = AudioPlayer(ffplay="C:\\tools\\ffplay.exe")
    player.start(r"C:\media dir\my video.mp4")
    (cmd, kwargs), = fake_popen["calls"]

    assert cmd[0] == "C:\\tools\\ffplay.exe"
    assert "-vn" in cmd
    assert "-nodisp" in cmd
    assert "-autoexit" in cmd
    assert "-stats" in cmd
    assert "-loglevel" in cmd
    assert "warning" in cmd
    assert cmd[-1] == r"C:\media dir\my video.mp4"  # path is one argument
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.PIPE
    assert player._process is fake_popen["proc"]


def test_start_passes_path_as_single_arg(fake_popen):
    player = AudioPlayer(ffplay="ffplay")
    player.start(r"C:\dir with spaces\clip video.mp4")
    (cmd, _), = fake_popen["calls"]
    # The path containing spaces must remain a single command element.
    assert cmd[-1] == r"C:\dir with spaces\clip video.mp4"
    assert len(cmd) == 8


def test_stop_terminates_and_waits(fake_popen):
    player = AudioPlayer(ffplay="ffplay")
    player.start("video.mp4")
    player.stop()
    proc = fake_popen["proc"]
    assert proc.terminated == 1
    assert proc.killed == 0
    assert player._process is None  # cleared so it is idempotent


def test_stop_idempotent(fake_popen):
    player = AudioPlayer(ffplay="ffplay")
    player.start("video.mp4")
    player.stop()
    player.stop()  # second call must be a no-op
    assert fake_popen["proc"].terminated == 1


def test_ffplay_media_clock_parses_stats():
    player = AudioPlayer(ffplay="ffplay", now=lambda: 12.0)
    import io
    player._read_stats(io.BytesIO(b"  7.250 M-A:  0.003 fd=  0\r"))
    assert player.media_position() == pytest.approx(7.250)
    assert player.sync_drift == pytest.approx(0.003)


def test_ffplay_media_clock_extrapolates_while_running(fake_popen):
    now = [10.0]
    player = AudioPlayer(ffplay="ffplay", now=lambda: now[0])
    import io
    player._read_stats(io.BytesIO(b"  2.000 M-A:  0.000\r"))
    player._process = fake_popen["proc"]
    now[0] = 10.125
    assert player.media_position() == pytest.approx(2.125)


def test_stop_skips_already_exited(fake_popen):
    fake_popen["proc"]._exited = True  # ffplay already exited on its own
    player = AudioPlayer(ffplay="ffplay")
    player.start("video.mp4")
    player.stop()
    assert fake_popen["proc"].terminated == 0  # no need to terminate


def test_is_running_false_when_no_process():
    assert AudioPlayer(ffplay="ffplay").is_running() is False


def test_is_running_true_while_alive(fake_popen):
    player = AudioPlayer(ffplay="ffplay")
    player.start("video.mp4")
    assert player.is_running() is True


def test_missing_ffplay_raises(fake_popen):
    # Explicitly simulate a machine where FFplay is unavailable.
    # The patch must cover AudioPlayer construction because the default
    # FFplay executable is resolved during initialization.
    with mock.patch("src.audio.shutil.which", return_value=None):
        player = AudioPlayer(ffplay=None)

        with pytest.raises(FFplayNotFoundError) as excinfo:
            player.start("video.mp4")

    assert fake_popen["calls"] == []  # never tried to launch
    msg = str(excinfo.value)
    assert "required for audio" in msg
    assert "RGB_ASCII_NO_AUDIO" in msg
    assert "https://ffmpeg.org/download.html" in msg


def test_kill_after_timeout(fake_popen):
    proc = fake_popen["proc"]

    def _wait(timeout=None):
        raise subprocess.TimeoutExpired(cmd="ffplay", timeout=timeout)

    proc.wait = _wait
    player = AudioPlayer(ffplay="ffplay")
    player.start("video.mp4")
    player.stop()
    assert proc.terminated == 1
    assert proc.killed == 1


def test_has_audio_stream_true_when_output_present():
    result = mock.Mock()
    result.stdout = b"audio\n"
    with mock.patch("src.audio.subprocess.run", return_value=result) as m:
        assert has_audio_stream("video.mp4", ffprobe="ffprobe") is True
    args = m.call_args.args[0]
    assert args[0] == "ffprobe"
    assert "-select_streams" in args and "a" in args
    assert "video.mp4" in args


def test_has_audio_stream_false_when_no_output():
    result = mock.Mock()
    result.stdout = b""
    with mock.patch("src.audio.subprocess.run", return_value=result):
        assert has_audio_stream("video.mp4", ffprobe="ffprobe") is False


def test_has_audio_stream_failsafe_when_ffprobe_missing():
    with mock.patch("src.audio.shutil.which", return_value=None):
        assert has_audio_stream("video.mp4") is True  # attempt playback


def test_run_stops_audio_on_cleanup():
    """The playback loop must stop FFplay even on normal EOF.

    With the M5 completion policy, on normal EOF the loop first lets FFplay
    exit naturally within a bounded wait, and then guarantees cleanup by
    stopping any still-running process. Here FFplay never exits on its own, so
    the safety net must terminate it.
    """
    from src.config import Config
    from src.main import run
    from src.renderer import RGBAsciiRenderer
    from src.sync import AudioStatus, PlaybackTimeline
    import src.timing as timing

    class FakeReader:
        def __init__(self):
            self._n = 0
            self.width = 2
            self.height = 2

        def read_frame(self):
            self._n += 1
            return None if self._n > 2 else bytes(2 * 2 * 3)

        def close(self):
            pass

    class FakeTerminal:
        def write_frame(self, _f):
            pass

        def restore(self):
            pass

    class InstantTime:
        """A fake clock that makes wait_for_exit time out immediately."""

        def __init__(self):
            self.t = 0.0

        def now(self):
            return self.t

        def sleep(self, _s):
            self.t += 999.0  # jump well past any timeout deadline

    with mock.patch("src.audio.subprocess.Popen") as popen:
        proc = FakeProc()
        popen.return_value = proc
        ftime = InstantTime()
        audio = AudioPlayer(ffplay="ffplay", now=ftime.now, sleep_fn=ftime.sleep)
        audio.start("video.mp4")

        config = Config(enable_color=False, fps=1000)
        timeline = PlaybackTimeline(
            playback_start=0.0, audio_status=AudioStatus.CONFIRMED,
            audio_launched_at=0.0,
        )
        result = run(FakeReader(), RGBAsciiRenderer(config), FakeTerminal(),
                     timing.FrameClock(1000, sleep_fn=lambda _: None),
                     config, audio, timeline, media_duration=None)
    assert result == 0
    assert proc.terminated == 1  # safety-net cleanup stopped FFplay
    assert timeline.audio_waited_for_exit is True
