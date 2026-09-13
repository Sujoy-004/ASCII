"""Tests for Milestone: richer color rendering.

Covers the area-averaged (box) RGB sampler, gradient smoothing / banding
reduction, integer and non-integer scaling in both directions, valid ANSI
24-bit output, the unchanged luminance->glyph mapping, and the opt-in
half-block (U+2580) color mode.
"""

import random
import re

import pytest

from src.config import Config
from src.renderer import (
    RGBAsciiRenderer,
    _box_ranges,
    ansi_truecolor,
    char_for_brightness,
    luminance,
    resize_rgb24_area,
)


# ---------------------------------------------------------------------------
# Reference implementation: the mathematical definition, written independently
# of the optimized path (direct pixel accumulation, no row-slice optimizations).
# ---------------------------------------------------------------------------

def _ref_ranges(src_size, dst_size):
    if src_size >= dst_size:
        return [
            (d * src_size // dst_size, (d + 1) * src_size // dst_size)
            for d in range(dst_size)
        ]
    return [
        (d * src_size // dst_size, d * src_size // dst_size + 1)
        for d in range(dst_size)
    ]


def _ref_box(frame, sw, sh, dw, dh):
    xs = _ref_ranges(sw, dw)
    ys = _ref_ranges(sh, dh)
    out = bytearray(dw * dh * 3)
    pos = 0
    for y0, y1 in ys:
        for x0, x1 in xs:
            totals = [0, 0, 0]
            count = 0
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    o = (yy * sw + xx) * 3
                    totals[0] += frame[o]
                    totals[1] += frame[o + 1]
                    totals[2] += frame[o + 2]
                    count += 1
            for c in range(3):
                out[pos] = (2 * totals[c] + count) // (2 * count)
                pos += 1
    return bytes(out)


def _gray_frame(w, h, value):
    return bytes([value] * (w * h * 3))


# ---------------------------------------------------------------------------
# 1. Area-based RGB sampling
# ---------------------------------------------------------------------------

def test_box_ranges_tile_source_exactly():
    """Downscale: ranges are contiguous, ordered, gap-free and cover [0, src).
    Upscale: every destination sample names exactly one source pixel
    (nearest-equivalent) that stays within [0, src)."""
    for src, dst in [(3, 2), (5, 3), (16, 7), (9, 4), (10, 10)]:
        ranges = _box_ranges(src, dst)
        assert len(ranges) == dst
        assert ranges[0][0] == 0
        assert ranges[-1][1] == src
        for (p0, p1), (n0, n1) in zip(ranges, ranges[1:]):
            assert p0 < p1 and p1 == n0  # contiguous, ordered, non-empty
    for src, dst in [(7, 16), (4, 9), (8, 8)]:
        for r0, r1 in _box_ranges(src, dst):
            assert r1 - r0 == 1          # single-pixel samples
            assert 0 <= r0 < src
        starts = [r0 for r0, _ in _box_ranges(src, dst)]
        assert starts == sorted(starts)  # sample points never backtrack


def test_area_average_exact_2x2_to_1x1():
    frame = bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120])
    # pixel(0,0)=(10,20,30) (0,1)=(40,50,60) (1,0)=(70,80,90) (1,1)=(100,110,120)
    out = resize_rgb24_area(frame, 2, 2, 1, 1)
    assert out == bytes([55, 65, 75])  # exact channel means (55, 65, 75)


def test_area_average_matches_reference_random():
    """The optimized sampler is byte-identical to the direct reference box
    average across random frames and a range of integer/non-integer scales."""
    random.seed(21)
    for _ in range(40):
        sw = random.randint(2, 9)
        sh = random.randint(2, 9)
        dw = random.randint(1, 6)
        dh = random.randint(1, 6)
        frame = bytes(random.randrange(256) for _ in range(sw * sh * 3))
        expected = _ref_box(frame, sw, sh, dw, dh)
        assert resize_rgb24_area(frame, sw, sh, dw, dh) == expected, (
            f"mismatch {sw}x{sh} -> {dw}x{dh}"
        )


# ---------------------------------------------------------------------------
# 2. Non-integer source -> terminal scaling
# ---------------------------------------------------------------------------

def test_non_integer_scaling_exact_values():
    """3x3 -> 2x2: partitions are (0,1),(1,3) per axis, so the bottom-right
    cell is the mean of a genuine 2x2 region."""
    # value(r,c) = r*3+c as a gray pixel (v,v,v), 9 pixels = 27 bytes
    frame = bytes(
        v for r in range(3) for c in range(3) for v in (r * 3 + c,) * 3
    )
    out = resize_rgb24_area(frame, 3, 3, 2, 2)
    # dst(0,0)=src(0,0)=0 ; dst(0,1)=mean(1,2)=round(1.5)=2
    # dst(1,0)=mean(3,6)=round(4.5)=5 ; dst(1,1)=mean(4,5,7,8)=6
    assert out == bytes([0, 0, 0, 2, 2, 2, 5, 5, 5, 6, 6, 6])


def test_non_integer_scaling_preserves_total_luminance_trend():
    """A strictly increasing gradient downscaled by a non-integer factor keeps
    the same ordering and stays within the source's per-cell means."""
    w, h = 7, 3
    src = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            v = x * 30 + y * 5
            o = (y * w + x) * 3
            src[o] = src[o + 1] = src[o + 2] = v
    out = resize_rgb24_area(bytes(src), w, h, 2, 2)
    for i in range(0, len(out), 3):
        assert out[i] == out[i + 1] == out[i + 2]
    cells = [out[i] for i in range(0, len(out), 3)]
    # means increase along the x gradient; check per output row, since rows are
    # stacked (a bottom-left region may average lower than a top-right one)
    for row in (cells[:2], cells[2:]):
        assert row == sorted(row)  # monotonic means preserved per row


# ---------------------------------------------------------------------------
# 3. Upscaling / downscaling
# ---------------------------------------------------------------------------

def test_upscale_copies_covered_source_pixels():
    """2x2 -> 4x4: each destination cell covers exactly one source pixel (there
    is nothing to average), equivalent to nearest-neighbor."""
    frame = bytes([
        10, 20, 30, 40, 50, 60,   # row 0: (10,20,30) (40,50,60)
        70, 80, 90, 100, 110, 120,  # row 1: (70,80,90) (100,110,120)
    ])
    out = resize_rgb24_area(frame, 2, 2, 4, 4)
    # sample points: dst cols 0,1 -> src 0 ; cols 2,3 -> src 1 (same for rows)
    rows = [out[y * 12:(y + 1) * 12] for y in range(4)]
    top = bytes([10, 20, 30, 10, 20, 30, 40, 50, 60, 40, 50, 60])
    bot = bytes([70, 80, 90, 70, 80, 90, 100, 110, 120, 100, 110, 120])
    assert rows[0] == rows[1] == top
    assert rows[2] == rows[3] == bot

def test_downscale_averages_region():
    """6x6 -> 2x2 with an exact 3x3 partition: each output cell is the mean of
    a 3x3 source block."""
    w, h = 6, 6
    frame = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            v = y * w + x          # 0..35
            o = (y * w + x) * 3
            frame[o] = frame[o + 1] = frame[o + 2] = v
    out = resize_rgb24_area(bytes(frame), w, h, 2, 2)
    # block(0,0): values 0..2 rows, 0..2 cols -> 0,1,2,6,7,8,12,13,14 mean 63/9=7
    # block(1,1): rows 3..5, cols 3..5 -> 21,22,23,27,28,29,33,34,35 mean 252/9=28
    assert out[:3] == bytes([7, 7, 7])
    assert out[9:12] == bytes([28, 28, 28])


def test_same_dimensions_returns_original():
    frame = bytes([1, 2, 3] * 4)
    assert resize_rgb24_area(frame, 2, 2, 2, 2) is frame


def test_area_average_rejects_invalid_length():
    with pytest.raises(ValueError):
        resize_rgb24_area(bytes(3), 2, 2, 1, 1)


# ---------------------------------------------------------------------------
# 4. Gradients / banding reduction
# ---------------------------------------------------------------------------

def _linear_gradient(width, height):
    """Horizontal gray ramp from 0 to 255."""
    frame = bytearray(width * height * 3)
    for y in range(height):
        for x in range(width):
            v = round(x * 255 / (width - 1))
            o = (y * width + x) * 3
            frame[o] = frame[o + 1] = frame[o + 2] = v
    return bytes(frame)


def test_area_gradient_is_monotonic_and_smooth():
    src = _linear_gradient(64, 1)
    out = resize_rgb24_area(src, 64, 1, 16, 1)
    vals = [out[i] for i in range(0, len(out), 3)]
    assert vals == sorted(vals)          # no reversal across the ramp
    assert vals[0] < 40 and vals[-1] > 215  # covers the range
    deltas = [b - a for a, b in zip(vals, vals[1:])]
    # adjacent width-4 region means differ by ~= 255*4/63 ≈ 16; large jumps
    # (banding) would show far bigger steps, so cap the max step well below
    # what point sampling can produce (a quarter-ramp jump is ~64).
    assert max(deltas) <= 20


def test_area_gradient_beats_point_sampling_max_step():
    """Point sampling an aligned ramp can emit a full 0->1 sub-run step of ~255
    (adjacent samples near the top can differ by ~64 for a 64->16 reduction);
    area averaging bounds every step to the region size (<= ~17 here)."""
    src = _linear_gradient(64, 1)
    out = resize_rgb24_area(src, 64, 1, 16, 1)
    vals = [out[i] for i in range(0, len(out), 3)]
    max_step = max(b - a for a, b in zip(vals, vals[1:]))
    assert max_step <= 263 // 16 + 2      # region-length bound, far under 64


def test_two_dimensional_gradient_average_is_region_mean():
    src = _linear_gradient(8, 8)
    out = resize_rgb24_area(src, 8, 8, 2, 2)
    expected = _ref_box(src, 8, 8, 2, 2)
    assert out == expected


# ---------------------------------------------------------------------------
# 5. Valid ANSI 24-bit output on rendered frames
# ---------------------------------------------------------------------------

_ANSI_COLOR_RE = re.compile(r"(?:38|48);2;(\d+);(\d+);(\d+)m")


def _parse_colors(out):
    """All 24-bit RGB triples in a rendered frame (foreground + background)."""
    return [tuple(map(int, m)) for m in _ANSI_COLOR_RE.findall(out)]


def test_render_resized_frame_emits_averaged_ansi_colors():
    cfg = Config(enable_color=True)
    renderer = RGBAsciiRenderer(cfg)
    sw = sh = 4
    src = _linear_gradient(sw, sh)
    out = renderer.render_resized_frame(src, sw, sh, 2, 2)
    colors = _parse_colors(out)
    expected = resize_rgb24_area(src, sw, sh, 2, 2)
    assert len(colors) == 4                    # one per destination cell
    exp_colors = [tuple(expected[i:i + 3]) for i in range(0, len(expected), 3)]
    assert colors == exp_colors                # ANSI RGB == area-averaged RGB
    for c in colors:
        assert all(0 <= v <= 255 for v in c)


def test_ansi_colors_are_24bit_not_palette_derived():
    frame = bytes([1, 2, 3, 250, 200, 150, 40, 41, 42, 77, 88, 99])
    cfg = Config(enable_color=True)
    out = RGBAsciiRenderer(cfg).render_frame(frame, 2, 2)
    colors = _parse_colors(out)
    assert (1, 2, 3) in colors and (250, 200, 150) in colors  # preserved 24-bit


def test_glyph_mapping_unchanged_from_averaged_rgb():
    """Luminance is still derived from the (averaged) RGB via the same Rec. 601
    mapping; the emitted glyph equals char_for_brightness(luminance(r,g,b))."""
    cfg = Config(enable_color=True, chars="ab")
    renderer = RGBAsciiRenderer(cfg)
    # The averaged pixel (127,127,127) maps to the very same glyph+color the
    # original renderer would output for that RGB value: mapping is unchanged.
    averaged = bytes([127, 127, 127])
    out = renderer.render_frame(averaged, 1, 1)
    assert out == ansi_truecolor(127, 127, 127) + char_for_brightness(
        luminance(127, 127, 127), cfg.chars
    ) + "\x1b[0m"


def test_no_color_render_still_uses_luminance_glyph_only():
    cfg = Config(enable_color=False)
    renderer = RGBAsciiRenderer(cfg)
    out = renderer.render_frame(bytes([80, 80, 80]), 1, 1)
    assert "\x1b[" not in out
    assert out == char_for_brightness(luminance(80, 80, 80), cfg.chars)


# ---------------------------------------------------------------------------
# 6. Half-block (U+2580) opt-in rendering
# ---------------------------------------------------------------------------

def test_blocks_render_doubles_vertical_density():
    cfg = Config(enable_color=True)
    renderer = RGBAsciiRenderer(cfg)
    # 2 wide x 4 tall source becomes 2 rows of 2 block cells.
    frame = bytes(range(2 * 4 * 3))
    out = renderer.render_frame_blocks(frame, 2, 2)
    lines = out.split("\n")
    assert len(lines) == 2
    assert "▀" in out
    colors = _parse_colors(out)
    # 4 cells x 2 color slots (fg + bg) = 8 color triples
    assert len(colors) == 8


def test_blocks_foreground_background_pairing():
    cfg = Config(enable_color=True)
    renderer = RGBAsciiRenderer(cfg)
    # one cell: top pixel (10,20,30), bottom pixel (200,100,50)
    frame = bytes([10, 20, 30, 200, 100, 50])
    out = renderer.render_frame_blocks(frame, 1, 1)
    assert (10, 20, 30) in _parse_colors(out)
    assert (200, 100, 50) in _parse_colors(out)


def test_blocks_rejects_wrong_frame_height():
    cfg = Config(enable_color=True)
    renderer = RGBAsciiRenderer(cfg)
    with pytest.raises(ValueError):
        renderer.render_frame_blocks(bytes(9), 1, 1)


def test_blocks_resize_path_area_averages():
    cfg = Config(enable_color=True)
    renderer = RGBAsciiRenderer(cfg)
    # 2x2 source -> 1x1 display needs a 2-tall target: a single ▀ cell pairing
    # the area-average of the top two pixels with the bottom two.
    frame = bytes([10, 10, 10, 20, 20, 20, 30, 30, 30, 40, 40, 40])
    out = renderer.render_resized_blocks_frame(frame, 2, 2, 1, 1)
    colors = _parse_colors(out)
    assert (15, 15, 15) in colors  # top band mean
    assert (35, 35, 35) in colors  # bottom band mean