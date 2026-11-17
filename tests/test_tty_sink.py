"""TTY-fit sizing and dual-mode stdout sink tests for the headless CLI.

UAT Gap 1 coverage: real-terminal playback must fit the terminal and redraw
in place (screen clear + cursor-home animation), while piped, redirected, or
captured output stays byte-identical plain text. Everything here is
hermetic -- no real terminal, no real FFmpeg.
"""

from __future__ import annotations

import io

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
