"""Cleanup must survive whatever happens inside the cleanup path itself.

Everything here guards a `finally` block. A `finally` that raises while cleaning
up is worse than no cleanup at all: it skips the remaining steps, so the failure
that is least recoverable is the one a crash mid-teardown causes.
"""

from __future__ import annotations

import io
import subprocess

import pytest

from src.audio import AudioPlayer
from src.config import Config
from src.main import run
from src.renderer import RGBAsciiRenderer
from src.sync import PlaybackTimeline
from src.timing import FrameClock

FRAME = bytes(4 * 4 * 3)


class FakeTime:
    def __init__(self, start: float = 1000.0):
        self.t = start
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


class WarmupReader:
    def __init__(self, frames: list[bytes], timestamps=None):
        self._frames = list(frames)
        self.closed = False
        self.height = 4
        self.width = 4
        self.launched_at = 0.0
        self.media_timestamps = tuple(timestamps or ())

    def read_frame(self) -> bytes | None:
        return self._frames.pop(0) if self._frames else None

    def close(self) -> None:
        self.closed = True


class FakeTerminal:
    def __init__(self) -> None:
        self.restored = False

    def refresh_size(self) -> bool:
        return False

    def output_size(self, _aspect: float) -> tuple[int, int]:
        return (4, 4)

    def write_frame(self, _frame) -> None:
        pass

    def restore(self) -> None:
        self.restored = True


# ---------------------------------------------------------------------------
# AudioPlayer.stop() runs from a `finally`, so it must not raise
# ---------------------------------------------------------------------------


class HostileProc:
    """A process that fails every way a real one might, during teardown."""

    def __init__(self) -> None:
        self.stderr = self
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0

    def poll(self):
        return None  # still running

    def terminate(self) -> None:
        self.terminate_calls += 1
        raise OSError("no such process")

    def kill(self) -> None:
        self.kill_calls += 1
        raise OSError("no such process")

    def wait(self, timeout=None) -> int:
        self.wait_calls += 1
        raise subprocess.TimeoutExpired("ffplay", timeout or 0)

    def close(self) -> None:
        raise OSError("bad fd")


def test_stop_survives_a_process_that_fails_every_teardown_call():
    ft = FakeTime()
    player = AudioPlayer(ffplay="ffplay", now=ft.now, sleep_fn=ft.sleep)
    player._process = HostileProc()

    player.stop()  # must not raise

    # And the player must be left disarmed, so a second stop is a no-op rather
    # than a second round of failures.
    assert player._process is None
    player.stop()
    assert player._process is None


def test_stop_closes_stderr_even_when_the_process_never_ran():
    """A dead FFplay with an unread stderr pipe still must not leak the fd."""

    class AlreadyGone:
        def __init__(self) -> None:
            self.stderr = io.BytesIO()
            self.terminated = 0

        def poll(self):
            return 0

        def terminate(self) -> None:
            self.terminated += 1

    ft = FakeTime()
    player = AudioPlayer(ffplay="ffplay", now=ft.now, sleep_fn=ft.sleep)
    proc = AlreadyGone()
    player._process = proc

    player.stop()

    assert proc.terminated == 0  # already exited, so no signal sent
    assert proc.stderr.closed


def test_stop_joins_the_stats_thread_without_hanging_on_a_stuck_one():
    """A stats thread wedged on a blocking read must not wedge `stop()`."""

    class StuckThread:
        def join(self, timeout=None) -> None:
            raise RuntimeError("cannot join thread before it is started")

    ft = FakeTime()
    player = AudioPlayer(ffplay="ffplay", now=ft.now, sleep_fn=ft.sleep)
    player._process = HostileProc()
    player._stats_thread = StuckThread()

    player.stop()  # must not raise

    assert player._stats_thread is None


# ---------------------------------------------------------------------------
# run()'s teardown must survive an interrupt raised inside the teardown
# ---------------------------------------------------------------------------


class InterruptingAudio:
    """Audio whose graceful EOF wait is interrupted -- a second Ctrl+C."""

    def __init__(self) -> None:
        self.stopped = False
        self.is_running_calls = 0

    @property
    def launched_at(self):
        return 0.0

    @property
    def sync_drift(self):
        return 0.0

    @property
    def exit_code(self):
        return 0

    @property
    def exit_at(self):
        return 1.0

    def media_position(self):
        return None

    def is_running(self) -> bool:
        self.is_running_calls += 1
        return True

    def wait_for_exit(self, timeout=None) -> bool:
        raise KeyboardInterrupt

    def stop(self) -> None:
        self.stopped = True


def _run(ft, frames, audio, media_duration=1.0, reader=None):
    """Drive run() and return (clock, stats-less terminal, audio)."""
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    terminal = FakeTerminal()
    result = run(
        reader if reader is not None else WarmupReader(frames),
        RGBAsciiRenderer(Config(enable_color=False, fps=1000)),
        terminal,
        clock,
        Config(enable_color=False, fps=1000),
        audio,
        PlaybackTimeline(playback_start=ft.t),
        media_duration=media_duration,
    )
    return result, terminal


def test_a_second_interrupt_during_the_eof_wait_still_cleans_up():
    """Ctrl+C during FFplay's graceful wait must not skip stop() and restore().

    The wait sits in `finally`, between two other teardown steps. Letting its
    KeyboardInterrupt escape would leave FFplay running and the cursor hidden,
    and the user would have to kill the process by hand.
    """
    ft = FakeTime()
    audio = InterruptingAudio()

    result, terminal = _run(ft, [FRAME] * 3, audio)

    assert audio.stopped
    assert terminal.restored
    # The second interrupt is honoured, and the run still reports success: the
    # user asked to leave, and nothing failed.
    assert result == 0


def test_a_second_interrupt_during_the_eof_wait_is_reported_as_an_interrupt(
    capsys,
):
    """Honouring the interrupt still means telling the user they interrupted.

    Silently swallowing it would misreport how playback ended.
    """
    ft = FakeTime()
    audio = InterruptingAudio()

    _run(ft, [FRAME] * 3, audio)

    assert "Interrupted by user" in capsys.readouterr().err


@pytest.mark.parametrize("frames", [[], [FRAME]])
def test_teardown_is_reachable_with_no_frames_at_all(frames):
    """Zero frames is still a playback run, so it must still tear down."""
    ft = FakeTime()
    audio = InterruptingAudio()

    _, terminal = _run(ft, frames, audio)

    assert audio.stopped
    assert terminal.restored


def test_reader_is_closed_even_when_the_eof_wait_is_interrupted():
    ft = FakeTime()
    audio = InterruptingAudio()
    reader = WarmupReader([FRAME] * 2)

    _run(ft, [], audio, reader=reader)

    assert reader.closed


def test_reader_and_terminal_are_both_released_when_the_decoder_raises():
    """A decoder failure must not leak the pipe or leave the cursor hidden."""
    ft = FakeTime()

    class ExplodingReader(WarmupReader):
        def read_frame(self):
            raise ValueError("decode failed")

    reader = ExplodingReader([])
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    terminal = FakeTerminal()

    # The error still propagates, so the caller can report it.
    with pytest.raises(ValueError):
        run(
            reader,
            RGBAsciiRenderer(Config(enable_color=False, fps=1000)),
            terminal,
            clock,
            Config(enable_color=False, fps=1000),
            None,
            None,
            media_duration=1.0,
        )

    assert reader.closed
    assert terminal.restored
