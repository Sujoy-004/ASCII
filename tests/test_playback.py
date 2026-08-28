"""Tests for the Milestone 2 continuous playback loop.

Uses fakes for the reader/terminal and the real renderer and FrameClock so the
loop, EOF handling, timing integration, and cleanup can be tested
deterministically without wall-clock or subprocess dependence.
"""

from src.config import Config
from src.main import run
from src.renderer import RGBAsciiRenderer
from src.timing import FrameClock


def _noop_sleep(_seconds):
    pass


class FakeReader:
    """Returns a scripted sequence of frames, then EOF."""

    def __init__(self, frames, width=8, height=8, raise_on=None):
        self._frames = list(frames)
        self.width = width
        self.height = height
        self.closed = False
        self.read_count = 0
        self._raise_on = raise_on

    def read_frame(self):
        self.read_count += 1
        if self._raise_on is not None and self.read_count >= self._raise_on:
            raise KeyboardInterrupt
        if not self._frames:
            return None
        return self._frames.pop(0)

    def close(self):
        self.closed = True


class FakeTerminal:
    def __init__(self):
        self.written = 0
        self.restored = False

    def write_frame(self, _frame_string):
        self.written += 1

    def restore(self):
        self.restored = True


def _black_frame(width=8, height=8):
    return bytes(width * height * 3)


def _clock(fps=30):
    return FrameClock(fps, sleep_fn=_noop_sleep)


def test_continuous_frame_consumption():
    frames = [_black_frame() for _ in range(5)]
    reader = FakeReader(frames)
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=1000)
    result = run(reader, RGBAsciiRenderer(config), terminal, _clock(1000),
                 config)
    assert result == 0
    assert reader.read_count == 6          # 5 frames + 1 EOF probe
    assert terminal.written == 5           # all frames rendered


def test_eof_terminates_cleanly():
    reader = FakeReader([_black_frame()] * 3)
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=1000)
    result = run(reader, RGBAsciiRenderer(config), terminal, _clock(1000),
                 config)
    assert result == 0
    assert terminal.written == 3
    assert reader.closed
    assert terminal.restored


def test_no_frames_exits_cleanly():
    reader = FakeReader([])
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=1000)
    result = run(reader, RGBAsciiRenderer(config), terminal, _clock(1000),
                 config)
    assert result == 0
    assert terminal.written == 0


def test_loop_invokes_timing_clock():
    """The loop must consult FrameClock (via wait_until), not bypass it."""
    frames = [_black_frame() for _ in range(4)]
    reader = FakeReader(frames)
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=30)

    class RecordingClock(FrameClock):
        def __init__(self):
            super().__init__(30, sleep_fn=_noop_sleep)
            self.waits = 0

        def wait_until(self, deadline, proc_start=None):
            self.waits += 1
            return 0.0  # deterministic: never actually sleep

    clock = RecordingClock()
    run(reader, RGBAsciiRenderer(config), terminal, clock, config)
    assert clock.waits == 4             # once per rendered frame


def test_cleanup_after_end_frame():
    """Cleanup runs even after the last frame, not only on errors."""
    reader = FakeReader([_black_frame()])
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=1000)
    run(reader, RGBAsciiRenderer(config), terminal, _clock(1000), config)
    assert reader.closed
    assert terminal.restored


def test_cleanup_on_interrupt():
    """Ctrl+C mid-playback must still run cleanup."""
    reader = FakeReader(
        [_black_frame()] * 3, raise_on=2  # third read raises KeyboardInterrupt
    )
    terminal = FakeTerminal()
    config = Config(enable_color=False, fps=1000)
    result = run(reader, RGBAsciiRenderer(config), terminal, _clock(1000),
                 config)
    assert result == 0
    assert reader.closed      # FFmpeg stopped
    assert terminal.restored  # cursor restored
