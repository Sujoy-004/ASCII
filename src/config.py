"""Configuration for the RGB ASCII renderer.

All tunable settings live here so the rendering pipeline never hard-codes
magic values. A single dataclass instance is passed through the components.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Default luminance-to-character gradient: low brightness first, high last.
DEFAULT_CHARS = " .:-=+*#%@"

# Named luminance-to-character gradients selectable via PRESET. Each is a
# luminance ramp from darkest (index 0) to brightest (index len-1). An explicit
# CHARS override always wins over a preset.
CHAR_PRESETS: dict[str, str] = {
    "default": DEFAULT_CHARS,
    # Dense: many grayscale ramps, subtle midtone steps (classic 10-step).
    "dense": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    # Simple: a coarse but instantly readable low-value ramp.
    "simple": " .:-=+*#%@",
    # Blocks: filled block elements for high-contrast monochrome rendering.
    "blocks": " \u2591\u2592\u2593\u2588",
}


@dataclass
class Config:
    """Runtime configuration for the ASCII video renderer."""

    # Character gradient used for luminance -> ASCII mapping. Index 0 is the
    # darkest character, index len-1 the brightest.
    chars: str = DEFAULT_CHARS

    # Name of the active character preset (None when a custom CHARS override
    # or the default is in use). Informational for --debug.
    preset: str | None = None

    # Target frames per second for rendering.
    fps: int = 30

    # Aspect correction: terminal characters are typically taller than wide.
    # Value is char_width / char_height. Used to preserve the source video's
    # visual aspect ratio when mapping pixels onto the character-cell grid.
    char_aspect: float = 0.5

    # Temporal smoothing factor (alpha, new-frame contribution) in [0, 1].
    # 0 disables smoothing (M6/M7 default, opt-in). 1.0 is "current frame"
    # immediately. Values in (0, 1) blend toward the current frame.
    smoothing: float = 0.0

    # Rows reserved below the render area, so playback stays inside the
    # viewport and the shell prompt can be restored without scrolling.
    status_rows: int = 2

    enable_audio: bool = True
    enable_color: bool = True
    debug: bool = False

    def __post_init__(self) -> None:
        if not self.chars:
            raise ValueError("chars gradient must not be empty")
        if self.fps <= 0:
            raise ValueError("fps must be positive")
        if not 0.0 <= self.smoothing <= 1.0:
            raise ValueError("smoothing must be in [0, 1]")
        if self.char_aspect <= 0:
            raise ValueError("char_aspect must be positive")
