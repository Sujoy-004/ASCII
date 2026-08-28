"""Tests for luminance and brightness-related logic."""

from src.renderer import char_for_brightness, luminance


def test_black_is_zero():
    assert luminance(0, 0, 0) == 0


def test_white_is_max():
    assert luminance(255, 255, 255) == 255


def test_gray_is_mid():
    assert 120 <= luminance(128, 128, 128) <= 135


def test_pure_red():
    # r=255 contributes highest weight among primaries.
    assert 70 <= luminance(255, 0, 0) <= 82


def test_brightness_endpoints():
    chars = " .:-=+*#%@"
    assert char_for_brightness(0, chars) == " "
    assert char_for_brightness(255, chars) == "@"


def test_brightness_intermediate():
    chars = " .:-=+*#%@"
    # Roughly half brightness must not equal either endpoint.
    mid = char_for_brightness(128, chars)
    assert mid not in (" ", "@")


def test_brightness_bounds_clamped():
    chars = "ab"
    assert char_for_brightness(-5, chars) == "a"
    assert char_for_brightness(999, chars) == "b"
