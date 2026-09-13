"""Tests for the Milestone 2 continuous playback loop.

Uses fakes for the reader/terminal and the real renderer and FrameClock so the
loop, EOF handling, timing integration, and cleanup can be tested
deterministically without wall-clock or subprocess dependence.
"""

import pytest

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
    def __init__(self, sizes=None, initial=(8, 8)):
        self.written = 0
        self.restored = False
        self.width, self.height = initial
        self._sizes = list(sizes or [initial])
        self.clears = 0

    def output_size(self, _video_aspect=None):
        return self.width, self.height

    def refresh_size(self):
        if self._sizes:
            size = self._sizes.pop(0)
        else:
            size = (self.width, self.height)
        changed = size != (self.width, self.height)
        self.width, self.height = size
        return changed

    def clear(self):
        self.clears += 1

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


def test_resize_changes_render_dimensions_without_resetting_clock():
    class RecordingRenderer:
        def __init__(self):
            self.calls = []

        def render_frame(self, frame, width, height):
            self.calls.append(("normal", width, height))
            return "frame"

        def render_resized_frame(self, frame, src_width, src_height, dst_width, dst_height):
            self.calls.append(("resized", src_width, src_height, dst_width, dst_height))
            return "frame"

    reader = FakeReader([_black_frame() for _ in range(3)])
    terminal = FakeTerminal(sizes=[(8, 8), (12, 10), (12, 10), (12, 10)])
    renderer = RecordingRenderer()
    config = Config(enable_color=False, fps=1000)
    clock = _clock(1000)
    clock_start = clock.current_time()

    result = run(reader, renderer, terminal, clock, config, video_aspect=1.0)

    assert result == 0
    assert renderer.calls == [
        ("normal", 8, 8),
        ("resized", 8, 8, 12, 10),
        ("resized", 8, 8, 12, 10),
    ]
    assert terminal.clears == 1
    assert clock.start_time == pytest.approx(clock_start)
    assert reader.closed


def test_resize_uses_latest_size_for_aspect_preserving_output():
    reader = FakeReader([_black_frame() for _ in range(2)])
    terminal = FakeTerminal(sizes=[(8, 8), (16, 12)])
    config = Config(enable_color=False, fps=1000)
    renderer = RGBAsciiRenderer(config)

    result = run(reader, renderer, terminal, _clock(1000), config, video_aspect=16 / 9)

    assert result == 0
    assert terminal.clears == 1
