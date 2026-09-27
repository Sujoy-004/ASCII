"""RGB pixel -> ASCII + ANSI True Color rendering.

This module is purely concerned with turning frames of RGB24 pixel data into
an ANSI-escaped string of characters. It knows nothing about FFmpeg, files,
or terminals.

Frame layout contract: a frame is a bytes-like object of length
width * height * 3, laid out row-major with 3 bytes per pixel (R, G, B).
"""

from __future__ import annotations

from functools import lru_cache

from src.config import Config

# ANSI escape prefix for true-color foreground.
_ANSI_COLOR = "\x1b[38;2;{r};{g};{b}m"
_ANSI_RESET = "\x1b[0m"

# Cache of per-gradient character lookup tables (256 entries: brightness->char).
# Keyed by the gradient string; rebuilt lazily so custom gradients stay correct
# and the always-on default gradient is computed only once.
_char_table_cache: dict[str, str] = {}

# Precomputed ASCII decimal string for every byte value, used to build ANSI
# color sequences without per-pixel str.format (M8 hot path).
_decimal_str = tuple(str(i) for i in range(256))


def char_table_for(chars: str) -> str:
    """Return the 256-entry (brightness -> char) lookup table for a gradient.

    The table is equivalent to applying ``char_for_brightness`` to every value
    in [0, 255]: index clamped to [0, len(chars)-1]. Cached per gradient so
    repeated rendering never recomputes it.
    """
    table = _char_table_cache.get(chars)
    if table is None:
        gradient = len(chars) - 1
        table = "".join(
            chars[min(max(int(b * gradient / 255), 0), gradient)]
            for b in range(256)
        )
        _char_table_cache[chars] = table
    return table


def luminance(r: int, g: int, b: int) -> int:
    """Compute perceived luminance Y in [0, 255] using Rec. 601 weights."""
    return int(0.299 * r + 0.587 * g + 0.114 * b)


def char_for_brightness(brightness: int, chars: str) -> str:
    """Map a luminance value in [0, 255] to a character in the gradient.

    brightness 0 -> chars[0] (darkest), 255 -> chars[-1] (brightest).
    """
    gradient = len(chars) - 1
    index = int(brightness * gradient / 255)
    if index < 0:
        index = 0
    elif index > gradient:
        index = gradient
    return chars[index]


def ansi_truecolor(r: int, g: int, b: int) -> str:
    """Return the ANSI 24-bit foreground escape sequence for the RGB color."""
    return _ANSI_COLOR.format(r=r, g=g, b=b)


def pixel_index(x: int, y: int, width: int) -> int:
    """Return the byte offset of the pixel at (x, y) in an RGB24 frame."""
    return (y * width + x) * 3


def frame_size(width: int, height: int) -> int:
    """Return the byte length of a width x height RGB24 frame."""
    return width * height * 3


def resize_rgb24(
    frame: bytes,
    src_width: int,
    src_height: int,
    dst_width: int,
    dst_height: int,
) -> bytes:
    """Resize an RGB24 frame with nearest-neighbor sampling.

    This is intentionally dependency-free so live terminal resizing can adapt
    already-decoded frames without restarting FFmpeg or changing the playback
    clock. When dimensions are unchanged, the original frame is returned.
    """
    if src_width <= 0 or src_height <= 0 or dst_width <= 0 or dst_height <= 0:
        raise ValueError("frame dimensions must be positive")
    expected = src_width * src_height * 3
    if len(frame) != expected:
        raise ValueError(
            f"RGB24 frame length {len(frame)} does not match "
            f"{src_width}x{src_height} ({expected})"
        )
    if (src_width, src_height) == (dst_width, dst_height):
        return frame

    src = memoryview(frame)
    out = bytearray(dst_width * dst_height * 3)
    x_offsets = [(x * src_width // dst_width) * 3 for x in range(dst_width)]
    src_row_bytes = src_width * 3
    out_pos = 0
    for y in range(dst_height):
        src_row = (y * src_height // dst_height) * src_row_bytes
        for src_x in x_offsets:
            out[out_pos:out_pos + 3] = src[src_row + src_x:src_row + src_x + 3]
            out_pos += 3
    return bytes(out)


@lru_cache(maxsize=None)
def _box_ranges(src_size: int, dst_size: int) -> tuple[tuple[int, int], ...]:
    """Partition ``src_size`` into ``dst_size`` sampling ranges.

    Downscaling (src >= dst): destination index ``d`` covers source indices
    ``[d * src // dst, (d + 1) * src // dst)``. The ranges tile the source
    exactly (in order, no gaps or overlaps), so every destination sample owns a
    well-defined area of the source -- the region a downscaled cell represents.

    Upscaling (src < dst): a destination pixel never covers a whole source
    pixel, so there is nothing to average; each destination sample takes the
    single source pixel containing its sample point ``d * src // dst``
    (nearest-equivalent copy).
    """
    if src_size >= dst_size:
        return tuple(
            (d * src_size // dst_size, (d + 1) * src_size // dst_size)
            for d in range(dst_size)
        )
    return tuple(
        (d * src_size // dst_size, d * src_size // dst_size + 1)
        for d in range(dst_size)
    )


def resize_rgb24_area(
    frame: bytes,
    src_width: int,
    src_height: int,
    dst_width: int,
    dst_height: int,
) -> bytes:
    """Resize an RGB24 frame with exact area (box) averaging.

    Each destination pixel is the unweighted mean of the entire source region
    it covers (partitioned by ``_box_ranges``), so the color of every cell
    reflects its whole source area rather than one arbitrary pixel. This smooths
    gradients and suppresses the per-cell color snapping that point sampling
    produces on sub-cell detail.

    When a destination dimension is not smaller than the source, the covered
    region is a single source pixel and its value is copied (there is nothing
    to average); that makes upscaling equivalent to nearest-neighbor. Identical
    dimensions return the original frame object unchanged.
    """
    if src_width <= 0 or src_height <= 0 or dst_width <= 0 or dst_height <= 0:
        raise ValueError("frame dimensions must be positive")
    expected = src_width * src_height * 3
    if len(frame) != expected:
        raise ValueError(
            f"RGB24 frame length {len(frame)} does not match "
            f"{src_width}x{src_height} ({expected})"
        )
    if (src_width, src_height) == (dst_width, dst_height):
        return frame

    x_ranges = _box_ranges(src_width, dst_width)
    y_ranges = _box_ranges(src_height, dst_height)
    src_row_bytes = src_width * 3
    # Split the source into one contiguous plane per channel once, instead of
    # building a strided ``seg[0::3]`` view per cell per row. Slicing contiguous
    # ``bytes`` is what makes the inner ``sum`` calls hit CPython's fast path:
    # summing a strided memoryview falls back to per-element buffer access and
    # costs roughly 1.5x more. Output is byte-for-byte identical either way.
    r_plane = frame[0::3]
    g_plane = frame[1::3]
    b_plane = frame[2::3]
    out = bytearray(dst_width * dst_height * 3)
    pos = 0
    for y0, y1 in y_ranges:
        rows = y1 - y0
        for x0, x1 in x_ranges:
            cols = x1 - x0
            if rows == 1 and cols == 1:
                o = y0 * src_row_bytes + x0 * 3
                out[pos] = r_plane[o // 3]
                out[pos + 1] = g_plane[o // 3]
                out[pos + 2] = b_plane[o // 3]
            else:
                n = rows * cols
                r_sum = g_sum = b_sum = 0
                base = y0 * src_width + x0
                for _ in range(rows):
                    end = base + cols
                    r_sum += sum(r_plane[base:end])
                    g_sum += sum(g_plane[base:end])
                    b_sum += sum(b_plane[base:end])
                    base += src_width
                out[pos] = (2 * r_sum + n) // (2 * n)
                out[pos + 1] = (2 * g_sum + n) // (2 * n)
                out[pos + 2] = (2 * b_sum + n) // (2 * n)
            pos += 3
    return bytes(out)


class RGBAsciiRenderer:
    """Converts RGB24 frames into ANSI-colored ASCII frame strings."""

    def __init__(self, config: Config) -> None:
        self.config = config
        # Precompute the per-gradient char table once per renderer instance.
        self._char_table = char_table_for(config.chars)

    def _render_uncolored(self, frame: bytes, width: int, height: int) -> str:
        table = self._char_table
        lines: list[str] = []
        for y in range(height):
            row = y * width * 3
            row_bits: list[str] = []
            append = row_bits.append
            for x in range(width):
                offset = row + x * 3
                bright = luminance(frame[offset], frame[offset + 1], frame[offset + 2])
                append(table[bright])
            lines.append("".join(row_bits))
        return "\n".join(lines)

    def _render_colored(self, frame: bytes, width: int, height: int) -> str:
        table = self._char_table
        dec = _decimal_str
        lines: list[str] = []
        reset = _ANSI_RESET
        for y in range(height):
            row = y * width * 3
            row_bits: list[str] = []
            append = row_bits.append
            for x in range(width):
                offset = row + x * 3
                r = frame[offset]
                g = frame[offset + 1]
                b = frame[offset + 2]
                bright = luminance(r, g, b)
                append("\x1b[38;2;" + dec[r] + ";" + dec[g] + ";" + dec[b] + "m" + table[bright])
            append(reset)
            lines.append("".join(row_bits))
        return "\n".join(lines)

    def render_frame(self, frame: bytes, width: int, height: int) -> str:
        """Render an RGB24 frame into a single ANSI frame string."""
        if self.config.enable_color:
            return self._render_colored(frame, width, height)
        return self._render_uncolored(frame, width, height)

    def render_frame_blocks(self, frame: bytes, width: int, height: int) -> str:
        """Render a ``width x (2*height)`` RGB24 frame as ``height`` half-block rows.

        Each terminal cell is the upper-half block U+2580 with the TOP source
        pixel as foreground and the BOTTOM single row below it as background,
        doubling vertical color density without growing the grid. Luminance
        mapping is intentionally bypassed here: the block glyph carries both
        colors, so the two source pixels are preserved independently.
        """
        expected = width * height * 2 * 3
        if len(frame) != expected:
            raise ValueError(
                f"RGB24 frame length {len(frame)} does not match "
                f"{width}x{2 * height} ({expected}) for half-block rendering"
            )
        if not self.config.enable_color:
            raise ValueError("half-block rendering requires color")
        dec = _decimal_str
        lines: list[str] = []
        for y in range(height):
            top_row = y * 2 * width * 3
            bot_row = top_row + width * 3
            row_bits: list[str] = []
            append = row_bits.append
            for x in range(width):
                o = x * 3
                tr = frame[top_row + o]
                tg = frame[top_row + o + 1]
                tb = frame[top_row + o + 2]
                br = frame[bot_row + o]
                bg = frame[bot_row + o + 1]
                bb = frame[bot_row + o + 2]
                append(
                    "\x1b[38;2;" + dec[tr] + ";" + dec[tg] + ";" + dec[tb]
                    + "m\x1b[48;2;" + dec[br] + ";" + dec[bg] + ";"
                    + dec[bb] + "m\u2580"
                )
            append(_ANSI_RESET)
            lines.append("".join(row_bits))
        return "\n".join(lines)

    def render_resized_frame(
        self,
        frame: bytes,
        src_width: int,
        src_height: int,
        dst_width: int,
        dst_height: int,
    ) -> str:
        """Resize an RGB24 frame with area averaging and render it."""
        resized = resize_rgb24_area(
            frame, src_width, src_height, dst_width, dst_height
        )
        return self.render_frame(resized, dst_width, dst_height)

    def render_resized_blocks_frame(
        self,
        frame: bytes,
        src_width: int,
        src_height: int,
        dst_width: int,
        dst_height: int,
    ) -> str:
        """Area-average to ``dst_width x (2*dst_height)`` and render half-block rows."""
        resized = resize_rgb24_area(
            frame, src_width, src_height, dst_width, dst_height * 2
        )
        return self.render_frame_blocks(resized, dst_width, dst_height)
