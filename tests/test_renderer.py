"""Tests for the RGB -> ASCII renderer and pixel frame math."""

import pytest

from src.config import DEFAULT_CHARS, Config
from src.renderer import (
    RGBAsciiRenderer,
    ansi_truecolor,
    char_for_brightness,
    char_table_for,
    frame_size,
    pixel_index,
)


def test_pixel_index():
    # width 10: pixel (0,0) at 0, (9,0) at 27, (0,1) at 30.
    assert pixel_index(0, 0, 10) == 0
    assert pixel_index(9, 0, 10) == 9 * 3
    assert pixel_index(0, 1, 10) == 10 * 3


def test_frame_size():
    assert frame_size(2, 2) == 12
    assert frame_size(120, 40) == 120 * 40 * 3


def test_ansi_construction():
    seq = ansi_truecolor(255, 0, 0)
    assert "\x1b[38;2;255;0;0m" in seq


def test_single_red_pixel_render():
    cfg = Config(enable_color=True)
    renderer = RGBAsciiRenderer(cfg)
    frame = bytes([255, 0, 0])  # one red pixel
    out = renderer.render_frame(frame, 1, 1)
    # True-color escape is present and the frame contains a gradient char.
    assert "\x1b[38;2;255;0;0m" in out
    assert ":" in out  # red luminance is low -> mid-low gradient char


def test_no_color_mode():
    cfg = Config(enable_color=False)
    renderer = RGBAsciiRenderer(cfg)
    frame = bytes([255, 255, 255])
    out = renderer.render_frame(frame, 1, 1)
    assert "\x1b[" not in out
    assert "@" in out


def test_frame_dimensions():
    cfg = Config(enable_color=False, chars="ab")
    renderer = RGBAsciiRenderer(cfg)
    # 2x2 frame, all zeros (black -> 'a'), no color codes.
    frame = bytes(2 * 2 * 3)
    out = renderer.render_frame(frame, 2, 2)
    rows = out.split("\n")
    assert len(rows) == 2
    assert all(len(row) == 2 for row in rows)


# ---------------------------------------------------------------------------
# M8 regression: the optimized lookup-table render must be byte-identical to
# the reference mapping for every possible luminance value and gradient.
# ---------------------------------------------------------------------------

def test_char_table_matches_char_for_brightness_default():
    table = char_table_for(DEFAULT_CHARS)
    for bright in range(256):
        assert table[bright] == char_for_brightness(bright, DEFAULT_CHARS)


def test_char_table_matches_char_for_brightness_custom():
    chars = "ab#"
    table = char_table_for(chars)
    for bright in range(256):
        assert table[bright] == char_for_brightness(bright, chars)


def test_char_table_cached_per_gradient():
    chars = " .:-=+*#%@"
    assert char_table_for(chars) is char_table_for(chars)


def test_lut_render_matches_reference_color_and_nocol():
    """The optimized renderer output is byte-identical to the pre-M8 output
    for both colored and uncolored paths across a non-trivial frame."""
    import random
    random.seed(9)
    w, h = 12, 7
    frame = bytes(random.randrange(256) for _ in range(w * h * 3))
    for enable_color in (True, False):
        cfg = Config(enable_color=enable_color)
        renderer = RGBAsciiRenderer(cfg)
        out = renderer.render_frame(frame, w, h)
        # reference: recompute per pixel exactly as the pre-M8 renderer did
        lines = []
        for y in range(h):
            row_chars = []
            row = y * w * 3
            for x in range(w):
                offset = row + x * 3
                r = frame[offset]; g = frame[offset + 1]; b = frame[offset + 2]
                bright = int(0.299 * r + 0.587 * g + 0.114 * b)
                ch = char_for_brightness(bright, cfg.chars)
                if enable_color:
                    row_chars.append(ansi_truecolor(r, g, b) + ch)
                else:
                    row_chars.append(ch)
            if enable_color:
                row_chars.append("\x1b[0m")
            lines.append("".join(row_chars))
        assert out == "\n".join(lines)


def test_resize_rgb24_nearest_neighbor():
    from src.renderer import resize_rgb24

    # Four distinct source pixels:
    # R G
    # B W
    frame = bytes([
        255, 0, 0,    0, 255, 0,
        0, 0, 255,    255, 255, 255,
    ])
    resized = resize_rgb24(frame, 2, 2, 4, 4)
    assert len(resized) == 4 * 4 * 3
    rows = [resized[y * 4 * 3:(y + 1) * 4 * 3] for y in range(4)]
    assert rows[0] == rows[1] == bytes([255, 0, 0] * 2 + [0, 255, 0] * 2)
    assert rows[2] == rows[3] == bytes([0, 0, 255] * 2 + [255, 255, 255] * 2)


def test_resize_rgb24_same_dimensions_returns_original():
    from src.renderer import resize_rgb24

    frame = bytes([1, 2, 3] * 4)
    assert resize_rgb24(frame, 2, 2, 2, 2) is frame

def test_resize_rgb24_rejects_invalid_frame_length():
    from src.renderer import resize_rgb24

    with pytest.raises(ValueError):
        resize_rgb24(bytes(3), 2, 2, 1, 1)
