"""Tests for the streaming timestamp probe (TimestampStream) and CFR detection.

A variable-rate source's PTS timeline used to be probed up front with a
blocking full-file ffprobe run, so the time to the first frame scaled with the
length of the video. ``TimestampStream`` produces the same timeline
incrementally: playback starts on the prefix already decoded and adopts the
rest as it arrives. These tests pin the producer's non-blocking
frame-index-to-media-time answers, its progressive validation, and the
constant-frame-rate fast path that skips enumeration entirely.

No real subprocesses are used: Popen is scripted with deterministic, gated
streams so a test can observe the timeline part-way through.
"""

import io
import threading
from unittest import mock

import pytest

from src.config import Config
from src.main import main, run
from src.renderer import RGBAsciiRenderer
from src.sync import TimestampStream, probe_video_rate
from src.timing import FrameClock

FRAME = bytes(2 * 2 * 3)  # one frame at the 2x2 reader size used below


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakePopen:
    """Scripted Popen stand-in for the timestamp probe subprocess."""

    def __init__(self, cmd=None, stdout=None, stderr=None):
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.terminated = 0
        self.killed = 0
        self._exit_code = None

    def poll(self):
        return self._exit_code

    def wait(self, timeout=None):
        return self._exit_code

    def terminate(self):
        self.terminated += 1
        self._exit_code = 1

    def kill(self):
        self.killed += 1
        self._exit_code = 1


class GatedStream:
    """File-like whose read() serves one line per opened gate, in order.

    A closed gate blocks read() as a real pipe would, so a test can freeze the
    timeline exactly where it needs to observe the prefix-answer behaviour.
    """

    def __init__(self, lines):
        self._lines = [line if line.endswith(b"\n") else line + b"\n" for line in lines]
        self.gates = [threading.Event() for _ in self._lines]
        self._pos = 0
        self.closed = False

    def release(self, count=1):
        opened = 0
        for gate in self.gates:
            if not gate.is_set() and opened < count:
                gate.set()
                opened += 1

    def release_all(self):
        self.release(len(self.gates))

    def read(self, size=-1):
        if self._pos >= len(self._lines):
            return b""
        self.gates[self._pos].wait()
        line = self._lines[self._pos]
        self._pos += 1
        return line

    def close(self):
        self.closed = True


def start_probe(lines, frame_duration=1 / 30, ffprobe="ffprobe"):
    """Start a TimestampStream against a scripted, gated ffprobe stream.

    Returns (proc, stream, gated). No line is served until the test releases
    its gate.
    """
    gated = GatedStream([line.encode() if isinstance(line, str) else line for line in lines])
    proc = FakePopen(stdout=gated, stderr=io.BytesIO())
    stream = TimestampStream("v.mp4", frame_duration=frame_duration, ffprobe=ffprobe)
    with mock.patch("src.sync.subprocess.Popen", return_value=proc):
        assert stream.start() is True
    return proc, stream, gated


class FakeTerminal:
    """Terminal stand-in for the main()/run() wiring tests."""

    def __init__(self, _config=None, size=(2, 2)):
        self.width, self.height = 40, 12
        self._size = size
        self.written = 0
        self.restored = 0

    def init(self):
        pass

    def output_size(self, _video_aspect=None):
        return self._size

    def refresh_size(self):
        return False

    def write_frame(self, _frame_string):
        self.written += 1

    def restore(self):
        self.restored += 1


def _probe_ok(stdout: bytes):
    result = mock.Mock()
    result.returncode = 0
    result.stdout = stdout
    return result


# ---------------------------------------------------------------------------
# CFR fast path
# ---------------------------------------------------------------------------


def test_probe_video_rate_cfr_integer_rates():
    stdout = b"r_frame_rate=30/1\navg_frame_rate=30/1\nnb_frames=300\nduration=10.000000\n"
    with mock.patch("src.sync.subprocess.run", return_value=_probe_ok(stdout)), \
         mock.patch("src.sync.shutil.which", return_value="ffprobe"):
        rate, is_cfr = probe_video_rate("v.mp4")
    assert is_cfr is True
    assert rate == pytest.approx(30.0)


def test_probe_video_rate_cfr_rational_rates():
    stdout = (
        b"r_frame_rate=24000/1001\navg_frame_rate=24000/1001\n"
        b"nb_frames=238\nduration=9.920000\n"
    )
    with mock.patch("src.sync.subprocess.run", return_value=_probe_ok(stdout)), \
         mock.patch("src.sync.shutil.which", return_value="ffprobe"):
        rate, is_cfr = probe_video_rate("v.mp4")
    # 9.92 * (24000/1001) = 237.84 frames, within tolerance of 238.
    assert is_cfr is True
    assert rate == pytest.approx(24000 / 1001)


def test_probe_video_rate_cfr_rejects_missing_frame_count():
    """A header that claims equal rates but prints N/A counts must NOT be
    trusted as CFR: a real VFR MKV was observed with exactly this shape."""
    stdout = b"r_frame_rate=30/1\navg_frame_rate=30/1\nnb_frames=N/A\nduration=N/A\n"
    with mock.patch("src.sync.subprocess.run", return_value=_probe_ok(stdout)), \
         mock.patch("src.sync.shutil.which", return_value="ffprobe"):
        assert probe_video_rate("v.mp4") == (None, False)


def test_probe_video_rate_cfr_rejects_disagreeing_rates():
    stdout = b"r_frame_rate=30/1\navg_frame_rate=30000/1001\nnb_frames=300\nduration=10.010000\n"
    with mock.patch("src.sync.subprocess.run", return_value=_probe_ok(stdout)), \
         mock.patch("src.sync.shutil.which", return_value="ffprobe"):
        assert probe_video_rate("v.mp4") == (None, False)


def test_probe_video_rate_cfr_rejects_frame_count_mismatch():
    stdout = b"r_frame_rate=30/1\navg_frame_rate=30/1\nnb_frames=200\nduration=10.000000\n"
    with mock.patch("src.sync.subprocess.run", return_value=_probe_ok(stdout)), \
         mock.patch("src.sync.shutil.which", return_value="ffprobe"):
        assert probe_video_rate("v.mp4") == (None, False)


def test_probe_video_rate_failsafe_when_ffprobe_missing():
    with mock.patch("src.sync.shutil.which", return_value=None):
        assert probe_video_rate("v.mp4") == (None, False)


def test_probe_video_rate_failsafe_on_failed_probe():
    result = mock.Mock(returncode=1, stdout=b"r_frame_rate=30/1\n")
    with mock.patch("src.sync.subprocess.run", return_value=result), \
         mock.patch("src.sync.shutil.which", return_value="ffprobe"):
        assert probe_video_rate("v.mp4") == (None, False)


# ---------------------------------------------------------------------------
# Producer answers are exactly the clock's three-branch model
# ---------------------------------------------------------------------------


def test_at_uses_the_grid_before_any_values_arrive():
    proc, stream, gated = start_probe([b"0.000000", b"0.040000"])
    # Nothing published yet: the fixed-FPS grid is the answer, non-blockingly.
    assert stream.at(0) == pytest.approx(0.0)
    assert stream.at(5) == pytest.approx(5 / 30)


def test_at_extrapolates_past_a_single_published_value():
    _, stream, gated = start_probe([b"10.040000", b"10.080000"])
    gated.release(1)
    assert stream.wait_ready(min_values=1, timeout=0.5)
    assert stream.at(0) == pytest.approx(0.0)
    # One value gives no inter-frame gap: later frames stay on the grid.
    assert stream.at(3) == pytest.approx(3 / 30)
    gated.release(1)
    assert stream.wait_ready(min_values=2, timeout=0.5)
    # Two values: past the prefix the source's own 0.040 gap is extended.
    assert stream.at(2) == pytest.approx(0.080)
    assert stream.at(3) == pytest.approx(0.120)


def test_at_tracks_progressively_published_vfr_values():
    _, stream, gated = start_probe(
        [b"0.000000", b"0.040000", b"0.080000", b"0.140000"])
    gated.release(3)
    assert stream.wait_ready(min_values=3, timeout=0.5)
    assert stream.at(1) == pytest.approx(0.040)
    assert stream.at(2) == pytest.approx(0.080)
    gated.release(1)
    assert stream.wait_ready(min_values=4, timeout=0.5)
    assert stream.at(3) == pytest.approx(0.140)
    assert stream.at(4) == pytest.approx(0.200)  # last gap 0.060, continued


def test_at_preserves_a_negative_first_pts():
    _, stream, gated = start_probe([b"-0.080000", b"-0.040000", b"0.000000"])
    gated.release_all()
    assert stream.wait_ready(min_values=3, timeout=0.5)
    assert stream.at(0) == pytest.approx(0.0)
    assert stream.at(1) == pytest.approx(0.040)
    assert stream.at(2) == pytest.approx(0.080)


def test_stream_matches_the_clock_for_the_same_prefix():
    """A stream wired into a clock must schedule every frame exactly as the
    fully probed tuple would -- the difference is only when values exist."""
    values = (0.0, 0.040, 0.080, 0.140)
    _, stream, gated = start_probe(
        [b"0.000000", b"0.040000", b"0.080000", b"0.140000"])
    gated.release_all()
    assert stream.wait_ready(min_values=4, timeout=0.5)

    tuple_clock = FrameClock(30, now=lambda: 0.0, sleep_fn=lambda _: None)
    tuple_clock.start(0.0)
    tuple_clock.set_media_timestamps(values)

    stream_clock = FrameClock(30, now=lambda: 0.0, sleep_fn=lambda _: None)
    stream_clock.start(0.0)
    stream_clock.set_timestamp_stream(stream)

    for i in range(2 * len(values) + 1):
        assert stream_clock.deadline(i) == pytest.approx(tuple_clock.deadline(i))


# ---------------------------------------------------------------------------
# Progressive validation (a bad row must not misalign later frames)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [b"N/A", b"", b"not-a-number", b"nan", b"inf", b"-inf"])
def test_a_bad_row_poisons_but_freezes_the_usable_prefix(bad):
    _, stream, gated = start_probe(
        [b"0.000000", b"0.040000", bad, b"0.100000"])
    gated.release_all()
    # Only the two valid rows can ever be published, so the wait times out.
    assert stream.wait_ready(min_values=3, timeout=0.25) is False
    assert stream.poisoned is True
    # The prefix stays exactly the good rows; the tail extends their cadence
    # rather than shifting onto the poison row's value.
    assert stream.at(0) == pytest.approx(0.0)
    assert stream.at(1) == pytest.approx(0.040)
    assert stream.at(2) == pytest.approx(0.080)


def test_out_of_order_row_poisons_the_stream():
    _, stream, gated = start_probe([b"0.000000", b"-0.040000"])
    gated.release_all()
    assert stream.wait_ready(min_values=2, timeout=0.25) is False
    assert stream.poisoned is True
    assert stream.at(0) == pytest.approx(0.0)
    # Single retained value, so the grid answers for the rest.
    assert stream.at(1) == pytest.approx(1 / 30)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_start_false_when_ffprobe_missing():
    with mock.patch("src.sync.shutil.which", return_value=None):
        stream = TimestampStream("v.mp4", frame_duration=1 / 30, ffprobe=None)
        assert stream.start() is False


def test_start_false_when_launch_fails_does_not_raise():
    stream = TimestampStream("v.mp4", frame_duration=1 / 30, ffprobe="ffprobe")
    with mock.patch("src.sync.subprocess.Popen", side_effect=OSError("no")):
        assert stream.start() is False
    stream.close()  # never started: must be a safe no-op


def test_wait_ready_returns_false_when_never_started():
    stream = TimestampStream("v.mp4", frame_duration=1 / 30, ffprobe="ffprobe")
    assert stream.wait_ready(min_values=2, timeout=0.01) is False


def test_wait_ready_returns_immediately_when_already_ready():
    _, stream, gated = start_probe([b"0.000000", b"0.040000"])
    gated.release_all()
    assert stream.wait_ready(min_values=2, timeout=0.5) is True
    assert stream.wait_ready(min_values=2, timeout=0.5) is True  # non-destructive


def test_wait_ready_bounds_the_tail():
    """A probe still warming up (no gate opened) must give up at the timeout,
    not block playback startup."""
    _, stream, gated = start_probe([b"0.000000", b"0.040000"])
    import time

    started = time.monotonic()
    assert stream.wait_ready(min_values=2, timeout=0.05) is False
    assert time.monotonic() - started < 0.5


def test_close_is_idempotent_and_terminates_a_running_probe():
    proc, stream, gated = start_probe([b"0.000000"])
    # No gate opened: the reader thread is parked and the probe is "running".
    stream.close()
    assert proc.terminated == 1
    assert proc.killed == 0
    assert stream.close() is None  # second close is a no-op, not a raise
    assert proc.terminated == 1


def test_close_is_safe_when_never_started():
    stream = TimestampStream("v.mp4", frame_duration=1 / 30, ffprobe="ffprobe")
    assert stream.close() is None


# ---------------------------------------------------------------------------
# Wiring: run() paces to the stream and closes it; main() launches it for VFR
# ---------------------------------------------------------------------------


class FakeTime:
    def __init__(self, start=0.0):
        self.t = start
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


class FakeReader:
    def __init__(self, frames, width=2, height=2):
        self._frames = list(frames)
        self.width = width
        self.height = height
        self.closed = False

    def read_frame(self):
        return self._frames.pop(0) if self._frames else None

    def close(self):
        self.closed = True


def test_start_false_when_the_stderr_sink_cannot_be_created(monkeypatch):
    """A failed stderr temp file keeps start() graceful and spawns no probe.

    The sink is created before Popen, so its own failure must not escape as an
    unbound-file error or half-launch a probe process.
    """
    stream = TimestampStream("v.mp4", frame_duration=1 / 30, ffprobe="ffprobe")
    monkeypatch.setattr(
        "src.sync.tempfile.TemporaryFile",
        lambda: (_ for _ in ()).throw(OSError(145, "No space left on device")),
    )
    with mock.patch("src.sync.subprocess.Popen") as popen:
        assert stream.start() is False
    popen.assert_not_called()
    stream.close()


def test_run_paces_to_a_wired_timestamp_stream():
    proc, stream, gated = start_probe([b"0.000000", b"0.400000"])
    gated.release_all()
    assert stream.wait_ready(min_values=2, timeout=0.5)

    ft = FakeTime()
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    config = Config(enable_color=False, fps=1000)
    terminal = FakeTerminal()
    reader = FakeReader([FRAME, FRAME])

    result = run(reader, RGBAsciiRenderer(config), terminal, clock, config,
                 timestamp_stream=stream)
    assert result == 0
    assert terminal.written == 2
    # Deadlines followed the source timestamps (0.0, 0.400), not the grid.
    assert ft.slept == [pytest.approx(0.400)]
    # run()'s finally closed the probe.
    assert proc.terminated == 1


def test_main_vfr_path_launches_and_closes_the_streaming_probe(tmp_path, monkeypatch, capsys):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not really a video")

    class FakeReaderProc:
        def __init__(self, cmd, **kwargs):
            self.stdout = io.BytesIO(FRAME * 3)
            self.stderr = kwargs["stderr"]

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    timestamp_proc = FakePopen(stdout=io.BytesIO(b"0.000000\n0.040000\n"))

    def popen_router(cmd, **kwargs):
        # sync and video share the same subprocess module, so one router
        # dispatches both: the decoders are "ffmpeg" invocations, the
        # timestamp probe is the "ffprobe" invocation.
        if cmd[0] == "ffmpeg":
            return FakeReaderProc(cmd, **kwargs)
        assert cmd[0] == "ffprobe", cmd
        return timestamp_proc

    monkeypatch.setattr("subprocess.Popen", popen_router)
    monkeypatch.setattr("src.video.shutil.which", lambda name: name)
    monkeypatch.setattr("src.sync.shutil.which", lambda name: name)
    monkeypatch.setattr("src.main.TerminalRenderer", FakeTerminal)
    monkeypatch.setattr("src.main.probe_media_duration", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_size", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_rate", lambda *a: (None, False))
    monkeypatch.delenv("RGB_ASCII_FPS", raising=False)
    monkeypatch.setenv("RGB_ASCII_NO_AUDIO", "1")
    monkeypatch.setenv("RGB_ASCII_DEBUG", "1")

    assert main([str(video)]) == 0
    # The stream was launched for the VFR path and closed on the way out.
    assert timestamp_proc.terminated == 1
    # The debug label reports the streaming timeline truthfully.
    assert "streaming source PTS" in capsys.readouterr().err


def test_main_vfr_path_label_degrades_when_the_probe_fails(tmp_path, monkeypatch, capsys):
    """A probe that cannot launch must be reported as unavailable.

    Before this guard the label read "streaming source PTS" even though the
    probe never started, so the clock ran on the fixed grid while the log
    claimed otherwise.
    """
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not really a video")

    class FakeReaderProc:
        def __init__(self, cmd, **kwargs):
            self.stdout = io.BytesIO(FRAME * 2)
            self.stderr = kwargs["stderr"]

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    def popen_router(cmd, **kwargs):
        if cmd[0] == "ffmpeg":
            return FakeReaderProc(cmd, **kwargs)
        raise OSError("ffprobe missing")

    monkeypatch.setattr("subprocess.Popen", popen_router)
    monkeypatch.setattr("src.video.shutil.which", lambda name: name)
    monkeypatch.setattr("src.sync.shutil.which", lambda name: name)
    monkeypatch.setattr("src.main.TerminalRenderer", FakeTerminal)
    monkeypatch.setattr("src.main.probe_media_duration", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_size", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_rate", lambda *a: (None, False))
    monkeypatch.delenv("RGB_ASCII_FPS", raising=False)
    monkeypatch.setenv("RGB_ASCII_NO_AUDIO", "1")
    monkeypatch.setenv("RGB_ASCII_DEBUG", "1")

    assert main([str(video)]) == 0
    assert "probe unavailable (fixed FPS fallback)" in capsys.readouterr().err


def test_main_cfr_path_does_not_launch_a_probe(tmp_path, monkeypatch, capsys):
    """A positively-CFR source must skip timestamp enumeration entirely.

    It also paces on the SOURCE's own rate (23.976 here), not the renderer's
    30 default: that is what makes a CFR source play at its natural speed,
    and the explicit RGB_ASCII_FPS override is the documented way to change it.
    """
    video = tmp_path / "cfr.mp4"
    video.write_bytes(b"not really a video")

    class FakeReaderProc:
        def __init__(self, cmd, **kwargs):
            self.stdout = io.BytesIO(FRAME * 2)
            self.stderr = kwargs["stderr"]

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    def popen_router(cmd, **kwargs):
        if cmd[0] == "ffmpeg":
            return FakeReaderProc(cmd, **kwargs)
        raise AssertionError("no ffprobe timestamp probe may launch for CFR")

    monkeypatch.setattr("subprocess.Popen", popen_router)
    monkeypatch.setattr("src.video.shutil.which", lambda name: name)
    monkeypatch.setattr("src.sync.shutil.which", lambda name: name)
    monkeypatch.setattr("src.main.TerminalRenderer", FakeTerminal)
    monkeypatch.setattr("src.main.probe_media_duration", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_size", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_rate", lambda *a: (23.976, True))
    monkeypatch.delenv("RGB_ASCII_FPS", raising=False)
    monkeypatch.setenv("RGB_ASCII_NO_AUDIO", "1")
    monkeypatch.setenv("RGB_ASCII_DEBUG", "1")

    assert main([str(video)]) == 0
    err = capsys.readouterr().err
    assert "23.976" in err, "CFR sources pace on their own detected rate"
    assert "fixed FPS (CFR metadata)" in err