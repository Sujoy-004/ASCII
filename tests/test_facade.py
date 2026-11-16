"""Tracer: end-to-end core engine rendering through the ``src`` facade.

Verifies the D-03 public package facade imports cleanly, that the full render
pipeline (``Config`` -> ``resize_rgb24_area`` -> ``render_frame``) works
without terminal dependencies, and that the terminal-only module is pruned
per D-01 (deleted from disk; ``src/main.py`` no longer references it).
"""

from __future__ import annotations

import sys
from pathlib import Path

import src
from src import (
    DEFAULT_CHARS,
    Config,
    RGBAsciiRenderer,
    char_table_for,
    luminance,
    resize_rgb24_area,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN_SOURCE = (REPO_ROOT / "src" / "main.py").read_text(encoding="utf-8")


def test_facade_exports_every_declared_symbol():
    """Every name in ``__all__`` is importable from ``src`` (D-03 contract)."""
    missing = [name for name in src.__all__ if not hasattr(src, name)]
    assert not missing, f"facade exports declared but absent: {missing}"


def test_core_symbols_import_directly_from_src():
    """The tracer's required imports resolve through the facade alone."""
    assert callable(src.RGBAsciiRenderer)
    assert callable(src.luminance)
    assert callable(src.resize_rgb24_area)
    assert callable(src.char_table_for)
    assert callable(src.Config)


def test_luminance_uses_rec601_weights():
    assert luminance(0, 0, 0) == 0
    assert luminance(255, 255, 255) == 255
    # Rec. 601: green dominates perceived brightness, blue contributes least.
    assert luminance(0, 255, 0) > luminance(0, 0, 255)


def test_config_and_renderer_construct():
    config = Config(enable_color=False)
    assert config.chars == DEFAULT_CHARS
    renderer = RGBAsciiRenderer(config)
    assert renderer.config is config
    assert len(char_table_for(DEFAULT_CHARS)) == 256


def test_end_to_end_frame_pipeline():
    """A synthetic 4x4 RGB24 frame rescales to 2x2 and renders as ASCII."""
    w = h = 4
    frame = bytearray()
    for y in range(h):
        for x in range(w):
            frame += bytes((255, 255, 255) if (x + y) % 2 == 0 else (0, 0, 0))
    frame = bytes(frame)
    assert len(frame) == w * h * 3

    resized = resize_rgb24_area(frame, w, h, 2, 2)
    assert len(resized) == 2 * 2 * 3
    # Each 2x2 destination cell averages two white and two black pixels.
    assert resized[0] == 128

    config = Config(enable_color=False)
    renderer = RGBAsciiRenderer(config)
    ascii_frame = renderer.render_frame(resized, 2, 2)
    assert isinstance(ascii_frame, str)
    assert len(ascii_frame.split("\n")) == 2
    # Every glyph comes from the configured luminance ramp (newlines are the
    # row separator, not glyphs).
    assert set(ascii_frame) - {"\n"} <= set(DEFAULT_CHARS)


def test_terminal_module_is_pruned_from_disk():
    """D-01: ``src/terminal.py`` is deleted, not archived."""
    assert not (REPO_ROOT / "src" / "terminal.py").exists()


def test_main_is_decoupled_from_terminal_renderer():
    """D-01: ``src/main.py`` has no TerminalRenderer import or reference."""
    assert "TerminalRenderer" not in MAIN_SOURCE
    assert "from src.terminal" not in MAIN_SOURCE
    assert "import src.terminal" not in MAIN_SOURCE


def test_facade_import_does_not_load_terminal_module():
    """The facade import chain never pulls the pruned terminal module."""
    assert "src.terminal" not in sys.modules
