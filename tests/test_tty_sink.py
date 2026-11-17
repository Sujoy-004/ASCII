"""TTY-fit sizing and dual-mode stdout sink tests for the headless CLI.

UAT Gap 1 coverage: real-terminal playback must fit the terminal and redraw
in place (screen clear + cursor-home animation), while piped, redirected, or
captured output stays byte-identical plain text. Everything here is
hermetic -- no real terminal, no real FFmpeg.
"""

from __future__ import annotations

import io

import pytest

import src.main
from src.config import Config

FRAME = bytes(2 * 2 * 3)  # one frame at the 2x2 reader size below


class FakeFFmpegProc:
    """Fake FFmpeg Popen result: scripted stdout, a fixed exit status."""

    def __init__(self, stdout_bytes=b"", returncode=0, stderr_text=b""):
        self.stdout = io.BytesIO(stdout_bytes)
        self.returncode = returncode
        self.stderr_text = stderr_text
        self.stderr_file = None

    def attach(self, stderr_file):
        self.stderr_file = stderr_file
        stderr_file.write(self.stderr_text)
        return self

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        pass

    def kill(self):
        pass

    @property
    def stdout_closed(self):
        return self.stdout.closed

    @property
    def stderr_closed(self):
        return self.stderr_file is not None and self.stderr_file.closed


def _run_tty(tmp_path, monkeypatch):
    """Run the real main() against a fake FFmpeg process with TTY seams patched.

    Mirrors tests/test_media_errors.py:_run_with (same monkeypatch set) and
    adds the TTY seams: stdout reports isatty True and the TTY-fit grid is
    pinned to the 2x2 size the fake frame stream provides. raising=False on
    the two TTY seam patches because they do not exist until the dual-mode
    sink feature lands (TDD RED compatibility); after GREEN they are patched
    normally.
    """
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not really a video")
    proc = FakeFFmpegProc(FRAME)  # one 2x2 RGB24 frame, then EOF

    monkeypatch.setattr(
        "src.video.subprocess.Popen", lambda cmd, **kw: proc.attach(kw["stderr"])
    )
    # The decoder resolves ffmpeg by name before spawning it; point that at a
    # path so the test does not need a real FFmpeg installed.
    monkeypatch.setattr("src.video.shutil.which", lambda name: name)
    # Piped-default grid pin (mirrors the (2,2) pins in test_media_errors.py).
    monkeypatch.setattr(
        "src.main._headless_output_size", lambda config, aspect: (2, 2)
    )
    monkeypatch.setattr("src.main.probe_media_duration", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_size", lambda *a, **k: None)
    monkeypatch.setattr("src.main.probe_video_rate", lambda *a, **k: (None, False))
    # TTY seams: pretend stdout is a real terminal and pin the TTY-fit grid
    # to the 2x2 size the fake frame stream is sized for.
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True, raising=False)
    monkeypatch.setattr(
        "src.main._tty_output_size", lambda config, aspect: (2, 2), raising=False
    )
    monkeypatch.setenv("RGB_ASCII_NO_AUDIO", "1")  # keep the CLI path audio-free
    monkeypatch.setenv("RGB_ASCII_FPS", "1000")
    return proc, src.main.main([str(video)])


def test_tty_run_animates_in_place_with_clear_home_and_hidden_cursor(
    tmp_path, monkeypatch, capsys
):
    """End-to-end TTY playback: clear + cursor-home + hidden cursor escape.

    Drives the real main() through the fake-FFmpeg pattern with the TTY seams
    patched; the sink must initialize the terminal in place instead of
    writing plain frames with a trailing newline.
    """
    _proc, code = _run_tty(tmp_path, monkeypatch)
    assert code == 0
    out = capsys.readouterr().out
    assert "\x1b[2J" in out, "screen clear must be emitted on the TTY path"
    assert "\x1b[H" in out, "cursor-home redraw must be emitted on the TTY path"
    assert "\x1b[?25l" in out, "cursor must be hidden on the TTY path"


def test_piped_output_is_byte_identical_plain_text(capsys):
    """Piped/redirected stdout: frame text + one newline, zero escape bytes.

    The pre-fix byte contract is authoritative for non-TTY runs: whatever the
    TTY path does, captured output must not change by a single byte.
    """
    sink = src.main._StdoutSink(Config())
    sink.write_frame("AB\nCD")
    sink.restore()
    captured = capsys.readouterr().out
    assert captured == "AB\nCD\n"
    assert "\x1b" not in captured, "no escape byte may reach piped output"


def test_tty_sizing_gate_returns_none_when_not_a_tty(monkeypatch):
    """_tty_output_size must gate on the TTY seam, not blind-size."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: False)
    assert src.main._tty_output_size(Config(), 16.0 / 9.0) is None


# ---------------------------------------------------------------------------
# Task 2: sizing-math exact values, live-resize protocol, and edge cases.
# All unit-level: monkeypatched seams only, never a real terminal.
# ---------------------------------------------------------------------------


def test_tty_sizing_width_limited_16_9_on_40x12(monkeypatch):
    """16:9 on a 40x12 terminal fills the width: (40, 11)."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True)
    monkeypatch.setattr("src.main._terminal_size", lambda: (40, 12))
    assert src.main._tty_output_size(Config(), 16.0 / 9.0) == (40, 11)


def test_tty_sizing_portrait_9_16_on_40x12(monkeypatch):
    """9:16 portrait on a 40x12 terminal is height-limited: (14, 12)."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True)
    monkeypatch.setattr("src.main._terminal_size", lambda: (40, 12))
    assert src.main._tty_output_size(Config(), 9.0 / 16.0) == (14, 12)


def test_tty_sizing_aspect_defaults_match_16_9(monkeypatch):
    """None and non-positive video_aspect both default to 16:9's grid."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True)
    monkeypatch.setattr("src.main._terminal_size", lambda: (80, 24))
    baseline = src.main._tty_output_size(Config(), 16.0 / 9.0)
    assert src.main._tty_output_size(Config(), None) == baseline
    assert src.main._tty_output_size(Config(), 0) == baseline


def test_tty_sizing_degenerate_terminal_returns_minimal_grid(monkeypatch):
    """A (1, 1) size report still yields a liveable (1, 1) grid, not zero."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True)
    monkeypatch.setattr("src.main._terminal_size", lambda: (1, 1))
    assert src.main._tty_output_size(Config(), 16.0 / 9.0) == (1, 1)


@pytest.mark.parametrize("avail_w,avail_h", [(80, 24), (40, 12), (100, 30)])
@pytest.mark.parametrize("aspect", [16.0 / 9.0, 9.0 / 16.0, 1.0])
def test_tty_sizing_respects_terminal_bounds(
    avail_w, avail_h, aspect, monkeypatch
):
    """The fitted grid never escapes the terminal in either dimension."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True)
    monkeypatch.setattr("src.main._terminal_size", lambda: (avail_w, avail_h))
    cols, rows = src.main._tty_output_size(Config(), aspect)
    assert 1 <= cols <= avail_w
    assert 1 <= rows <= avail_h


def test_refresh_size_detects_change_and_output_size_refits(
    monkeypatch, capsys
):
    """Live resize: changed-detection True + refit; unchanged probe False."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True)
    monkeypatch.setattr("src.main._terminal_size", lambda: (40, 12))
    sink = src.main._StdoutSink(Config())
    assert (sink.width, sink.height) == (40, 12)
    # The user resizes the terminal mid-play: re-probe must notice.
    monkeypatch.setattr("src.main._terminal_size", lambda: (50, 14))
    assert sink.refresh_size() is True
    assert sink.output_size(16.0 / 9.0) == (50, 14)
    # With no further resize, the next poll reports no change.
    assert sink.refresh_size() is False
    assert "\x1b" not in capsys.readouterr().out


def test_clear_emits_clear_home_only_after_first_frame(monkeypatch, capsys):
    """clear() erases the stale frame (clear + home) only once drawing began."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True)
    monkeypatch.setattr("src.main._terminal_size", lambda: (80, 24))
    sink = src.main._StdoutSink(Config())
    sink.clear()
    assert capsys.readouterr().out == "", "no clear before the first frame"
    sink.write_frame("AB")
    capsys.readouterr()
    sink.clear()
    assert capsys.readouterr().out == "\x1b[2J\x1b[H"


def test_non_tty_sink_members_are_inert(capsys):
    """A piped sink: refresh False, every member silent, zero escape bytes."""
    sink = src.main._StdoutSink(Config())
    assert sink.refresh_size() is False
    assert sink.output_size(16.0 / 9.0) == (0, 0)
    sink.clear()
    sink.restore()
    assert "\x1b" not in capsys.readouterr().out


def test_restore_is_idempotent(monkeypatch, capsys):
    """Overlapping cleanup paths cannot double-emit the cursor-show tail."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True)
    monkeypatch.setattr("src.main._terminal_size", lambda: (80, 24))
    sink = src.main._StdoutSink(Config())
    sink.write_frame("AB")
    capsys.readouterr()
    sink.restore()
    first = capsys.readouterr().out
    sink.restore()
    second = capsys.readouterr().out
    assert first == "\x1b[?25h\x1b[0m\n"
    assert second == ""


def test_single_initialization_across_two_frames(monkeypatch, capsys):
    """The terminal is initialized exactly once: one clear, one cursor-hide."""
    monkeypatch.setattr("src.main._stdout_is_tty", lambda: True)
    monkeypatch.setattr("src.main._terminal_size", lambda: (80, 24))
    sink = src.main._StdoutSink(Config())
    sink.write_frame("AB")
    sink.write_frame("CD")
    out = capsys.readouterr().out
    assert out.count("\x1b[2J") == 1
    assert out.count("\x1b[?25l") == 1
    assert out.count("\x1b[H") == 2
