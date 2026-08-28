"""Tests for automatic terminal-size adaptation and aspect-ratio preservation.

Verifies that the rendered grid fills the available viewport, preserves the
source video's visual aspect ratio after terminal-character aspect correction,
and reserves only the requested safety rows — across a range of terminal sizes.
"""

from unittest import mock

import pytest

from src.config import Config
from src.terminal import TerminalRenderer


def _term(width: int, height: int) -> TerminalRenderer:
    cfg = Config()  # char_aspect=0.5, status_rows=2
    with mock.patch.object(TerminalRenderer, "detect_size",
                           return_value=(width, height)):
        term = TerminalRenderer(cfg)
    return term


def _aspect(cols: int, rows: int, cfg: Config) -> float:
    # cols/rows * char_aspect must equal the source video aspect.
    return (cols / rows) * cfg.char_aspect


def test_fits_available_width_and_height():
    term = _term(80, 24)
    cols, rows = term.output_size(video_aspect=16 / 9)
    assert cols <= 80
    assert rows <= 24 - 2  # reserved status_rows


def test_16x9_preserved_on_80x24():
    term = _term(80, 24)
    cols, rows = term.output_size(video_aspect=16 / 9)
    assert _aspect(cols, rows, term.config) == pytest.approx(16 / 9, rel=0.02)


def test_16x9_preserved_on_large_terminal():
    term = _term(160, 50)
    cols, rows = term.output_size(video_aspect=16 / 9)
    assert cols == 160          # fills the width
    assert rows <= 50 - 2
    assert _aspect(cols, rows, term.config) == pytest.approx(16 / 9, rel=0.02)


def test_4x3_video_uses_more_height():
    term = _term(160, 50)
    cols4, rows4 = term.output_size(video_aspect=4 / 3)
    cols16, rows16 = term.output_size(video_aspect=16 / 9)
    # 4:3 is comparatively tall; it should use more rows than 16:9 at same width.
    assert rows4 > rows16
    assert _aspect(cols4, rows4, term.config) == pytest.approx(4 / 3, rel=0.02)


def test_default_aspect_used_when_unknown():
    term = _term(120, 40)
    cols, rows = term.output_size(video_aspect=None)
    assert _aspect(cols, rows, term.config) == pytest.approx(16 / 9, rel=0.02)
    cols2, rows2 = term.output_size(video_aspect=0)
    assert cols == cols2 and rows == rows2


def test_no_distortion_fill_priority_is_aspect_then_size():
    # Even a very tall/narrow terminal must not stretch to fill both dims.
    term = _term(60, 60)
    cols, rows = term.output_size(video_aspect=16 / 9)
    assert cols == 60                       # width limited
    assert rows <= 60 - 2
    assert _aspect(cols, rows, term.config) == pytest.approx(16 / 9, rel=0.02)
