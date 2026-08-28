"""Terminal control: size detection, ANSI state, buffered frame output.

This module owns the terminal: detecting dimensions, initializing/restoring
ANSI state, and writing complete frames. It never decodes video.
"""

from __future__ import annotations

import shutil
import sys

from src.config import Config

_CLEAR = "\x1b[2J"
_HOME = "\x1b[H"
_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_ANSI_RESET = "\x1b[0m"

# Assumed source aspect ratio (width/height) when it cannot be probed.
DEFAULT_VIDEO_ASPECT = 16.0 / 9.0


class TerminalRenderer:
    """Wraps a terminal's ANSI control and buffered output."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._initialized = False
        self.width, self.height = self.detect_size()

    @staticmethod
    def detect_size() -> tuple[int, int]:
        """Return the terminal (columns, lines) using the OS-reported size."""
        size = shutil.get_terminal_size((80, 24))
        return size.columns, size.lines

    def output_size(self, video_aspect: float | None = None) -> tuple[int, int]:
        """Derive ASCII render (columns, rows) fitting the terminal viewport.

        Uses the full available terminal area while preserving the source
        video's visual aspect ratio. Terminal characters are taller than wide,
        so ``char_aspect`` (cell width / height) corrects for that geometry:
        the rendered grid is chosen so that ``(cols / rows) * char_aspect``
        equals the source ``video_aspect``, filling the viewport in the
        limiting dimension and leaving only the minimal leftover in the other.

        ``video_aspect`` is the source pixel width / height. When it is
        unknown (None / non-positive) a 16:9 default is assumed. A few rows
        (``status_rows``) are reserved below the render area so a clean prompt
        can be restored without scrolling the terminal.
        """
        if video_aspect is None or video_aspect <= 0:
            video_aspect = DEFAULT_VIDEO_ASPECT
        avail_w = self.width
        avail_h = self.height - self.config.status_rows
        if avail_w < 1:
            avail_w = 1
        if avail_h < 1:
            avail_h = 1

        cf = self.config.char_aspect  # cell width / height
        # (cols * cf) / rows == video_aspect  ->  rows == cols * cf / video_aspect
        cols = min(avail_w, round(avail_h * video_aspect / cf))
        if cols < 1:
            cols = 1
        rows = round(cols * cf / video_aspect)
        if rows < 1:
            rows = 1
        if rows > avail_h:
            rows = avail_h
        if cols > avail_w:
            cols = avail_w
        return cols, rows

    def init(self) -> None:
        """Clear screen, home cursor, and hide the cursor."""
        self.write(_CLEAR + _HOME + _HIDE_CURSOR)
        self._initialized = True

    def restore(self) -> None:
        """Restore cursor visibility and styling, then move to a clean line.

        Idempotent: only acts while the terminal is initialized so cleanup
        paths can overlap without side effects. A trailing newline returns the
        shell prompt onto a fresh, non-scrolling line below the render area
        (the reserved ``status_rows`` keep it inside the viewport).
        """
        if not self._initialized:
            return
        self.write(_SHOW_CURSOR + _ANSI_RESET + "\n")
        self._initialized = False

    def write_frame(self, frame_string: str) -> None:
        """Redraw one frame: home the cursor (if initialized), then write.

        Builds a full redraw string and writes it in a single buffered flush.
        """
        if self._initialized:
            frame_string = _HOME + frame_string
        self.write(frame_string)

    def write(self, text: str) -> None:
        """Write text to stdout with a single buffered flush."""
        sys.stdout.write(text)
        sys.stdout.flush()
