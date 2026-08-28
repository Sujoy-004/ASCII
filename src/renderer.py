"""RGB pixel -> ASCII + ANSI True Color rendering.

This module is purely concerned with turning frames of RGB24 pixel data into
an ANSI-escaped string of characters. It knows nothing about FFmpeg, files,
or terminals.

Frame layout contract: a frame is a bytes-like object of length
width * height * 3, laid out row-major with 3 bytes per pixel (R, G, B).
"""

from __future__ import annotations

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

# Precomputed luminance -> character table for the default gradient, so the
# always-on DEFAULT_CHARS path avoids even a dict lookup (M8 hot path). Built
# on first use.
_DEFAULT_CHAR_TABLE: str | None = None


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


def _default_char_table() -> str:
    global _DEFAULT_CHAR_TABLE
    if _DEFAULT_CHAR_TABLE is None:
        _DEFAULT_CHAR_TABLE = char_table_for(" .:-=+*#%@")
    return _DEFAULT_CHAR_TABLE


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
