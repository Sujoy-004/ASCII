"""Tests for the final one-command CLI and its internal environment config.

The patient-facing interface is a single required positional video path:
  python -m src.main "PATH_TO_VIDEO"

plus one flag that is worth setting per run (--adaptive / --no-adaptive). Every
other development knob (fps, smoothing, presets, color/audio toggles, debug) is
configured through optional RGB_ASCII_* environment variables, so the public
CLI stays minimal without losing the ability to exercise those code paths.
"""

import re
from pathlib import Path

import pytest

from src.config import CHAR_PRESETS, DEFAULT_CHARS, Config
from src.main import build_parser, config_from_args
from src.renderer import RGBAsciiRenderer

MAIN_SOURCE = Path(__file__).resolve().parent.parent / "src" / "main.py"


def parse(*argv):
    return build_parser().parse_args(list(argv))


# ---------------------------------------------------------------------------
# One-command interface
# ---------------------------------------------------------------------------

def test_requires_exactly_one_video_argument():
    args = parse("vid.mp4")
    assert args.video == "vid.mp4"


def test_missing_video_argument_rejected():
    with pytest.raises(SystemExit):
        parse()


def test_no_public_flags_exposed():
    # Only the video path and the adaptive-quality flag are public; the internal
    # knobs stay behind RGB_ASCII_* so users are not tempted to configure them
    # manually.
    with pytest.raises(SystemExit):
        parse("vid.mp4", "--debug")
    with pytest.raises(SystemExit):
        parse("vid.mp4", "--preset", "dense")
    with pytest.raises(SystemExit):
        parse("vid.mp4", "--no-color")


# ---------------------------------------------------------------------------
# Adaptive quality flag
# ---------------------------------------------------------------------------

def test_adaptive_flag_defaults_to_unset_so_env_can_win():
    assert parse("vid.mp4").adaptive is None


def test_adaptive_flag_both_directions():
    assert parse("vid.mp4", "--adaptive").adaptive is True
    assert parse("vid.mp4", "--no-adaptive").adaptive is False


def test_no_adaptive_flag_beats_env(monkeypatch):
    """An explicit flag must override an inherited environment setting, in
    either direction -- otherwise a stray RGB_ASCII_NO_ADAPTIVE in a shell
    profile silently defeats the flag the user just typed."""
    args = parse("vid.mp4", "--no-adaptive")
    monkeypatch.setenv("RGB_ASCII_NO_ADAPTIVE", "1")
    assert config_from_args(args).adaptive_quality is False

    args = parse("vid.mp4", "--adaptive")
    monkeypatch.setenv("RGB_ASCII_NO_ADAPTIVE", "1")
    assert config_from_args(args).adaptive_quality is True


def test_adaptive_env_applies_when_flag_absent(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_NO_ADAPTIVE", "1")
    assert config_from_args(parse("vid.mp4")).adaptive_quality is False
    monkeypatch.delenv("RGB_ASCII_NO_ADAPTIVE")
    # The documented default stays adaptive when nothing says otherwise.
    assert config_from_args(parse("vid.mp4")).adaptive_quality is True


def test_adaptive_env_follows_the_same_truthiness_rule_as_every_other_bool():
    """All five RGB_ASCII_* booleans share one rule: any value outside the
    falsey set means "on". NO_ADAPTIVE must not invent a stricter rule of its
    own, or the same string would mean different things for --no-color and
    --no-adaptive."""
    falsey = ["", "0", "false", "no", "off", "FALSE", "Off"]
    truthy = ["1", "true", "yes", "on", "maybe"]  # unrecognised => still "on"
    for value in falsey:
        monkey = pytest.MonkeyPatch()
        monkey.setenv("RGB_ASCII_NO_ADAPTIVE", value)
        monkey.setenv("RGB_ASCII_NO_COLOR", value)
        try:
            config = config_from_args(parse("vid.mp4"))
            assert config.adaptive_quality is True, value
            assert config.enable_color is True, value
        finally:
            monkey.undo()
    for value in truthy:
        monkey = pytest.MonkeyPatch()
        monkey.setenv("RGB_ASCII_NO_ADAPTIVE", value)
        monkey.setenv("RGB_ASCII_NO_COLOR", value)
        try:
            config = config_from_args(parse("vid.mp4"))
            assert config.adaptive_quality is False, value
            assert config.enable_color is False, value
        finally:
            monkey.undo()


# ---------------------------------------------------------------------------
# Help text cannot drift from the code
# ---------------------------------------------------------------------------

def test_help_documents_every_env_var_the_code_reads():
    """--help advertises the RGB_ASCII_* surface, so a newly read variable that
    nobody documents would be invisible to users. Deriving the list from the
    source keeps the epilog honest without a second hand-maintained copy."""
    help_text = build_parser().format_help()
    read_by_code = set(re.findall(r"RGB_ASCII_[A-Z_]+", MAIN_SOURCE.read_text(encoding="utf-8")))
    assert read_by_code, "expected the source to reference RGB_ASCII_* vars"
    undocumented = sorted(v for v in read_by_code if v not in help_text)
    assert not undocumented, f"undocumented env vars in --help: {undocumented}"


def test_help_preset_names_match_the_real_presets():
    """The epilog names the presets a user can pass. An invented name is worse
    than no name: RGB_ASCII_PRESET silently falls back to the default for an
    unknown preset, so the typo looks like it worked."""
    help_text = build_parser().format_help()
    for name in CHAR_PRESETS:
        assert name in help_text, f"preset {name!r} missing from --help"


def test_video_argument_preserved_with_spaces():
    args = parse(r"C:\My Videos\clip with spaces.mp4")
    assert args.video == r"C:\My Videos\clip with spaces.mp4"


def test_absolute_external_path_preserved():
    args = parse(r"C:\Users\someone\Downloads\video.mp4")
    assert args.video == r"C:\Users\someone\Downloads\video.mp4"


# ---------------------------------------------------------------------------
# Sensible automatic defaults (no env set)
# ---------------------------------------------------------------------------

def test_defaults_are_sane(monkeypatch):
    for var in ("RGB_ASCII_PRESET", "RGB_ASCII_CHARS", "RGB_ASCII_FPS",
                "RGB_ASCII_SMOOTHING", "RGB_ASCII_NO_COLOR", "RGB_ASCII_NO_AUDIO",
                "RGB_ASCII_DEBUG", "RGB_ASCII_HALF_BLOCK"):
        monkeypatch.delenv(var, raising=False)
    cfg = config_from_args(parse("vid.mp4"))
    assert cfg.fps == 30
    assert cfg.smoothing == 0.0
    assert cfg.enable_color is True
    assert cfg.enable_audio is True
    assert cfg.debug is False
    assert cfg.blocks is False
    assert cfg.chars == DEFAULT_CHARS
    assert cfg.preset is None


# ---------------------------------------------------------------------------
# Internal env-var configuration
# ---------------------------------------------------------------------------

def test_env_preset_selects_gradient(monkeypatch):
    for name in ("default", "dense", "simple", "blocks"):
        monkeypatch.setenv("RGB_ASCII_PRESET", name)
        cfg = config_from_args(parse("vid.mp4"))
        assert cfg.chars == CHAR_PRESETS[name]
        assert cfg.preset == name


def test_env_chars_overrides_preset(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_PRESET", "blocks")
    monkeypatch.setenv("RGB_ASCII_CHARS", "ab")
    cfg = config_from_args(parse("vid.mp4"))
    assert cfg.chars == "ab"
    assert cfg.preset is None


def test_env_fps(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_FPS", "60")
    assert config_from_args(parse("vid.mp4")).fps == 60


def test_env_smoothing(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_SMOOTHING", "0.4")
    assert config_from_args(parse("vid.mp4")).smoothing == 0.4


def test_env_no_color(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_NO_COLOR", "1")
    assert config_from_args(parse("vid.mp4")).enable_color is False


def test_env_blocks_enables_half_block(monkeypatch):
    assert config_from_args(parse("vid.mp4")).blocks is False
    monkeypatch.setenv("RGB_ASCII_HALF_BLOCK", "1")
    assert config_from_args(parse("vid.mp4")).blocks is True


def test_env_no_audio(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_NO_AUDIO", "1")
    assert config_from_args(parse("vid.mp4")).enable_audio is False


def test_env_debug(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_DEBUG", "1")
    assert config_from_args(parse("vid.mp4")).debug is True


def test_env_preset_renders_usable_output(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_PRESET", "dense")
    monkeypatch.setenv("RGB_ASCII_NO_COLOR", "1")
    cfg = config_from_args(parse("vid.mp4"))
    renderer = RGBAsciiRenderer(cfg)
    out = renderer.render_frame(bytes([255, 0, 0]), 1, 1)
    assert "\x1b[" not in out       # no-color preserved
    assert len(out) == 1            # one gradient char


def test_invalid_env_fps_ignored(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_FPS", "abc")
    assert config_from_args(parse("vid.mp4")).fps == 30


def test_invalid_env_preset_ignored(monkeypatch):
    monkeypatch.setenv("RGB_ASCII_PRESET", "bogus")
    cfg = config_from_args(parse("vid.mp4"))
    assert cfg.chars == DEFAULT_CHARS
    assert cfg.preset is None


def test_smoothing_out_of_range_clamped_not_crash(monkeypatch):
    # Env-level values may bypass Config() dataclass validation; they must be
    # carried through and safely clamped downstream.
    monkeypatch.setenv("RGB_ASCII_SMOOTHING", "1.5")
    cfg = config_from_args(parse("vid.mp4"))
    assert cfg.smoothing == 1.5
    from src.smoothing import TemporalSmoother
    sm = TemporalSmoother(cfg)
    assert sm.alpha == 1.0           # clamped to safe range


# ---------------------------------------------------------------------------
# Config validation (dataclass-level, independent of CLI)
# ---------------------------------------------------------------------------

def test_negative_fps_rejected_by_config():
    with pytest.raises(ValueError):
        Config(fps=-5)


def test_smoothing_out_of_range_rejected_by_config():
    with pytest.raises(ValueError):
        Config(smoothing=1.5)
