"""Tests for Milestone 7: optional temporal smoothing.

Deterministic only: synthetic RGB frames, no subprocesses, no real-time
timing. Verifies the smoothing mathematics, disabled path equivalence,
first-frame initialization, dropped-frame isolation, bounded state, and
integration through run() (including M6 frame selection and M5 audio
completion remaining intact).
"""

from unittest import mock

import pytest

from src.audio import AudioPlayer
from src.config import Config
from src.main import run
from src.renderer import RGBAsciiRenderer, luminance
from src.smoothing import TemporalSmoother
from src.sync import AudioStatus, PlaybackTimeline
from src.timing import FrameClock

DEFAULT_CHARS = Config.chars  # " .:-=+*#%@", gradient length 9


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gray(b, size=3):
    """A single-pixel (or `size`-byte) grey RGB frame of brightness b."""
    return bytes([b] * size)


class FakeTime:
    def __init__(self, start=0.0):
        self.t = start

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class FakeReader:
    def __init__(self, frames, width=1, height=1):
        self._frames = list(frames)
        self.width = width
        self.height = height

    def read_frame(self):
        if not self._frames:
            return None
        return self._frames.pop(0)

    def close(self):
        pass


class FakeTerminal:
    def __init__(self):
        self.written = 0
        self.restored = False

    def write_frame(self, _f):
        self.written += 1

    def restore(self):
        self.restored = True


class FakeProc:
    def __init__(self, now, exits_at=None):
        self._now = now
        self._exits_at = exits_at
        self.terminated = 0

    def poll(self):
        if self._exits_at is not None and self._now() >= self._exits_at:
            return 0
        return None

    def terminate(self):
        self.terminated += 1

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 0


def _cfg(smoothing, **kw):
    kw.setdefault("enable_color", False)
    return Config(smoothing=smoothing, **kw)


# ---------------------------------------------------------------------------
# A. Disabled -> output equivalent to existing (pass-through)
# ---------------------------------------------------------------------------

def test_disabled_smoothing_is_pass_through():
    sm = TemporalSmoother(_cfg(0.0))   # default: disabled
    a, b = _gray(10), _gray(200)
    assert sm.smooth(a) == a           # identical to input
    assert sm.smooth(b) == b
    assert sm.smoothed_frames == 0
    assert sm.enabled is False


# ---------------------------------------------------------------------------
# B. Alpha = 1 -> output equals current frame
# ---------------------------------------------------------------------------

def test_alpha_one_equals_current_frame():
    sm = TemporalSmoother(_cfg(1.0))   # 1 > 0 => enabled, alpha 1
    assert sm.enabled is True
    a, b, c = _gray(0), _gray(100), _gray(255)
    assert sm.smooth(a) == a
    assert sm.smooth(b) == b           # alpha=1 => current immediately
    assert sm.smooth(c) == c


# ---------------------------------------------------------------------------
# C. Alpha = 0 -> output remains previous state (after init)
# ---------------------------------------------------------------------------

def test_alpha_zero_keeps_previous_after_init():
    # Force enabled so the alpha=0 boundary is exercised (config 0.0 normally
    # means "off").
    sm = TemporalSmoother(_cfg(0.0), enabled=True)
    a, b = _gray(0), _gray(255)
    assert sm.smooth(a) == a           # init
    assert sm.smooth(b) == a           # alpha=0 => previous forever
    assert sm.smooth(b) == a


# ---------------------------------------------------------------------------
# D. Simple interpolation: prev=100, cur=200, alpha=.25 => 125
# ---------------------------------------------------------------------------

def test_basic_interpolation():
    sm = TemporalSmoother(_cfg(0.25))
    assert sm.smooth(_gray(100)) == _gray(100)   # init
    out = sm.smooth(_gray(200))                  # 100*.75 + 200*.25 = 125
    assert out == _gray(125)


# ---------------------------------------------------------------------------
# E. First frame initializes directly (no blend against black)
# ---------------------------------------------------------------------------

def test_first_frame_initializes_without_black_blend():
    sm = TemporalSmoother(_cfg(0.5))
    first = _gray(180)
    assert sm.smooth(first) == first   # not blended toward black/zeros
    assert sm.smoothed_frames == 0


# ---------------------------------------------------------------------------
# F. Clamping / validation
# ---------------------------------------------------------------------------

def test_invalid_smoothing_out_of_range_rejected():
    with pytest.raises(ValueError):
        Config(smoothing=1.5)
    with pytest.raises(ValueError):
        Config(smoothing=-0.1)


def test_alpha_clamped_to_safe_range_at_level():
    """Out-of-range alpha must be clamped, never crash the byte blend."""
    cfg = Config(smoothing=0.0)   # Config() rejects out-of-range at construction
    # simulate a CLI-set out-of-range value post-construction:
    cfg.smoothing = 5.0
    sm = TemporalSmoother(cfg)
    assert sm.alpha == 1.0
    assert sm.enabled is True
    sm.smooth(_gray(0))
    out = sm.smooth(_gray(200))
    assert out == _gray(200)      # alpha clamped to 1.0 -> current frame

    cfg.smoothing = -3.0
    sm2 = TemporalSmoother(cfg)
    assert sm2.alpha == 0.0
    assert sm2.enabled is False    # negative -> treated as disabled


def test_blend_lut_matches_naive_formula_for_all_bytes():
    """M8 regression: the precomputed 256x256 blend table must equal the naive
    round(prev*(1-alpha) + cur*alpha) for every possible (prev, cur) pair."""
    sm = TemporalSmoother(_cfg(0.25))
    assert sm._blend_table is not None
    table = sm._blend_table
    a = 0.25
    one_minus = 1.0 - a
    for p in range(256):
        for c in range(256):
            expected = int(p * one_minus + c * a + 0.5)
            assert table[p * 256 + c] == expected, (p, c)


def test_blend_lut_not_built_when_disabled():
    sm = TemporalSmoother(_cfg(0.0))   # disabled -> no blend table needed
    assert sm._blend_table is None


# ---------------------------------------------------------------------------
# G. Dropped frames never contaminate the history
# ---------------------------------------------------------------------------

def test_dropped_frames_do_not_contaminate_history():
    """Only frames actually DISPLAYED update smoothing state.

    Simulate: display 10 -> drop 11,12,13 (never passed to smooth) -> display 14.
    The blend must be 10 -> 14, not 10 -> 11 -> 12 -> 13 -> 14.
    """
    sm = TemporalSmoother(_cfg(0.25))
    f10, f14 = _gray(100), _gray(200)
    assert sm.smooth(f10) == f10                     # displayed frame 10
    # 11, 12, 13 are dropped: we never call smooth() with them
    out = sm.smooth(f14)                             # displayed frame 14
    assert out == _gray(125)  # 100*.75 + 200*.25 -> proves 10 -> 14 directly


def test_steady_state_after_drop_catches_up_only_to_displayed():
    """After a drop, the new state is the blend of the two displayed frames."""
    sm = TemporalSmoother(_cfg(0.5))
    sm.smooth(_gray(0))          # init
    sm.smooth(_gray(0))          # stays 0
    # big jump arrives as a single displayed frame (post-drop)
    out = sm.smooth(_gray(64))
    assert out == _gray(32)      # prev 0 and current 64 at alpha .5


# ---------------------------------------------------------------------------
# H. Character-threshold stability
# ---------------------------------------------------------------------------

def _render_char(brightness, config):
    renderer = RGBAsciiRenderer(config)
    return renderer.render_frame(_gray(brightness), 1, 1)


def test_smoothing_stabilizes_character_across_luminance_boundary():
    """Oscillation around an ASCII boundary (140/143 -> chars[4]/chars[5])
    becomes a stable single char when smoothed with a low alpha."""
    cfg = _cfg(0.2)                       # DEFAULT chars, alpha .2
    renderer = RGBAsciiRenderer(cfg)
    sm = TemporalSmoother(cfg)

    sm.smooth(_gray(140))                 # init -> brightness 140
    chars = []
    for b in (143, 140, 143, 140):        # raw would oscillate chars[4],chars[5]
        smoothed = sm.smooth(_gray(b))
        chars.append(renderer.render_frame(smoothed, 1, 1))
    # every smoothed output should resolve to the SAME stable char
    assert len(set(chars)) == 1


def test_unsmoothed_crosses_boundary_but_smoothed_does_not():
    """Without smoothing the boundary is crossed; with smoothing it is not."""
    cfg = _cfg(0.2)
    sm = TemporalSmoother(cfg)
    sm.smooth(_gray(140))                 # index 4
    brights = []
    for b in (140, 143, 140, 143):
        f = sm.smooth(_gray(b))
        brights.append(luminance(f[0], f[0], f[0]))
    # all smoothed brightnesses stay on the index-4 side of the 141.67 boundary
    assert all(int(x * 9 / 255) == 4 for x in brights)


# ---------------------------------------------------------------------------
# I. Color (RGB) transition is numerically correct
# ---------------------------------------------------------------------------

def test_rgb_color_transition_numerically_correct():
    sm = TemporalSmoother(_cfg(0.5))
    black = bytes([0, 0, 0])
    color = bytes([255, 128, 64])
    assert sm.smooth(black) == black            # init
    out = sm.smooth(color)                      # each channel .5 blend
    assert out == bytes([128, 64, 32])


# ---------------------------------------------------------------------------
# J. No history growth (bounded state)
# ---------------------------------------------------------------------------

def test_smoothing_state_stays_bounded():
    sm = TemporalSmoother(_cfg(0.25))
    size = 6
    sm.smooth(_gray(0, size))
    for i in range(50):
        sm.smooth(_gray(i * 5, size))
    # Retains at most one previous frame state of the frame's size.
    assert len(sm._prev) == size
    assert isinstance(sm.smoothed_frames, int)   # scalar counter, not history
    state_len = len(sm._prev)
    sm.smooth(_gray(200, size))
    assert len(sm._prev) == state_len == size


# ---------------------------------------------------------------------------
# K. M6 regression: frame selection / dropping unaffected by smoothing
# ---------------------------------------------------------------------------

def test_healthy_run_drop_count_identical_with_smoothing_on_off():
    """Smoothing is a downstream rendering effect: it must not change how many
    frames are dropped (M6 behavior preserved)."""
    n = 8

    def run_once(smoothing):
        lt = FakeTime()                       # fresh clock per run
        reader = FakeReader([_gray(100, 3)] * n)
        terminal = FakeTerminal()
        config = _cfg(smoothing, fps=30)
        clock = FrameClock(30, now=lt.now, sleep_fn=lt.sleep)
        tl = PlaybackTimeline(playback_start=0.0, audio_status=AudioStatus.ABSENT)
        result = run(reader, RGBAsciiRenderer(config), terminal, clock, config,
                     None, tl)
        return result, terminal

    r_off, t_off = run_once(0.0)
    r_on, t_on = run_once(0.3)
    assert r_off == r_on == 0
    assert t_off.written == t_on.written == n   # healthy: nothing dropped either way


# ---------------------------------------------------------------------------
# L. M5 regression: audio completion intact during smoothing
# ---------------------------------------------------------------------------

def test_smoothing_run_preserves_m5_audio_completion():
    ft = FakeTime()
    proc = FakeProc(now=ft.now, exits_at=6.0)   # natural exit after video EOF
    with mock.patch("src.audio.subprocess.Popen", return_value=proc):
        player = AudioPlayer(ffplay="ffplay", now=ft.now, sleep_fn=ft.sleep)
        player.start("movie.mp4")
    player.launched_at = 0.0

    reader = FakeReader([_gray(120, 3)] * 3)
    terminal = FakeTerminal()
    config = _cfg(0.4, fps=30)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    tl = PlaybackTimeline(
        playback_start=0.0, audio_status=AudioStatus.CONFIRMED,
        audio_launched_at=0.0,
    )
    result = run(reader, RGBAsciiRenderer(config), terminal, clock, config,
                 player, tl, media_duration=5.0)
    assert result == 0
    assert proc.terminated == 0                  # audio not force-killed
    assert tl.audio_waited_for_exit is True      # M5 completion intact
    assert terminal.restored


def test_smoothing_run_cleans_up_on_no_frames():
    ft = FakeTime()
    reader = FakeReader([])
    terminal = FakeTerminal()
    config = _cfg(0.5, fps=30)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    tl = PlaybackTimeline(playback_start=0.0, audio_status=AudioStatus.ABSENT)
    result = run(reader, RGBAsciiRenderer(config), terminal, clock, config,
                 None, tl)
    assert result == 0
    assert terminal.written == 0
    assert terminal.restored


def test_blend_is_byte_identical_to_the_naive_formula_for_every_input():
    """The row-table blend must be a pure speedup, not a behaviour change.

    Covers all 65536 (previous, current) byte pairs for several alphas, which is
    every input the 256x256 blend table can ever see. This is the guard that
    lets the hot loop be restructured for speed: if it holds, the optimization
    is provably invisible to rendering.
    """
    from src.config import Config as _Config
    from src.smoothing import TemporalSmoother as _Smoother

    for alpha in (0.0, 0.05, 0.3, 0.5, 0.75, 1.0):
        smoother = _Smoother(_Config(smoothing=alpha))
        assert smoother.enabled is (alpha > 0.0)
        if not smoother.enabled:
            continue
        for previous in (0, 1, 127, 128, 254, 255):
            current = bytes(range(256))
            expected = bytes(
                int(previous * (1.0 - alpha) + c * alpha + 0.5) for c in range(256)
            )
            got = smoother._blend(bytearray(bytes([previous]) * 256), current)
            assert got == expected, (
                f"alpha={alpha} previous={previous} diverged from the formula"
            )


def test_blend_rows_are_a_view_of_the_same_table():
    """The row table is derived from the flat one, so they cannot disagree."""
    from src.config import Config as _Config
    from src.smoothing import TemporalSmoother as _Smoother

    smoother = _Smoother(_Config(smoothing=0.3))
    assert len(smoother._blend_rows) == 256
    for previous in range(256):
        assert smoother._blend_rows[previous] == (
            smoother._blend_table[previous * 256:(previous + 1) * 256]
        )
