"""Tests for the bounded adaptive quality controller.

Every scenario is driven by a deterministic list of per-frame work values, so
there is no timing flakiness: the controller only ever sees numbers.
"""

import pytest

from src.adaptive import (
    FULL,
    MAX_UTILIZATION,
    MONOCHROME,
    NO_SMOOTHING,
    QualityController,
    apply_level,
)


def drive(controller, work_list, budget=0.1):
    """Feed a work list, returning the level after each sample."""
    return [controller.record(w, budget) for w in work_list]


def test_single_outlier_cannot_flip_a_near_threshold_window():
    """One stalled frame moves a window's mean by at most MAX_UTILIZATION/window.

    The baseline sits just below the guaranteed-safe line
    (``down - MAX_UTILIZATION/window``) rather than far below the threshold, so
    this actually exercises the clamp instead of trivially passing.
    """
    c = QualityController(window=10, cooldown=20)
    safe = 0.85 - MAX_UTILIZATION / 10  # 0.65
    assert 0.5 < safe < 0.85, "baseline must be inside the band, not below it"
    # Nine frames at the safe baseline, one enormous spike (a GC pause, a
    # stalled decode, a terminal resize). The clamped mean stays under 0.85.
    levels = drive(c, [safe * 0.1] * 9 + [5.0])
    assert set(levels) == {FULL}, "one bad frame must not downgrade"


def test_sustained_overload_survives_the_clamp():
    """Clamping bounds single outliers, it must not hide real sustained load."""
    c = QualityController(window=10, cooldown=20)
    assert drive(c, [0.09] * 100)[-1] == MONOCHROME
    # 5x budget on *every* frame is still unambiguously overload.
    assert drive(c, [0.5] * 100)[-1] == MONOCHROME


def test_partial_window_never_changes_quality():
    c = QualityController(window=10, cooldown=20)
    assert set(drive(c, [10.0] * 9)) == {FULL}


def drive_until(controller, target, work, budget=0.1, limit=2000):
    """Feed constant ``work`` until the level reaches ``target``.

    Stops immediately on reaching it, so each test states only the condition it
    actually cares about instead of hard-coding a frame count.
    """
    for _ in range(limit):
        level = controller.record(work, budget)
        if level == target:
            return level
    raise AssertionError(f"never reached level {target} (stuck at {level})")


def test_sustained_pressure_downgrades_one_step_at_a_time():
    c = QualityController(window=10, cooldown=20)
    levels = drive(c, [0.09] * 100)  # 0.9 utilization, above the 0.85 threshold
    assert levels[-1] == MONOCHROME, "sustained overload reaches the bottom rung"
    # Every transition is a single step; the ladder is never jumped.
    transitions = [b - a for a, b in zip(levels, levels[1:]) if a != b]
    assert transitions and set(transitions) == {1}
    assert c.worst_level == MONOCHROME


def test_cooldown_suppresses_further_changes():
    # The first decision lands as soon as the first full window completes, and
    # the cooldown only bites after an actual change.
    c = QualityController(window=10, cooldown=30)
    levels = drive(c, [0.09] * 200)
    first = levels.index(NO_SMOOTHING)
    assert first == 9, "decides on the first complete window, not before"
    second = levels.index(MONOCHROME)
    assert second - first >= 30, "changes must respect the cooldown"


def test_hysteresis_leaves_intermediate_load_alone():
    # 0.65 utilization sits between up=0.5 and down=0.85, so it is undecided.
    c = QualityController(window=10, cooldown=20)
    assert set(drive(c, [0.065] * 200)) == {FULL}


def test_recovery_requires_sustained_low_utilization():
    c = QualityController(window=10, cooldown=20)
    drive_until(c, NO_SMOOTHING, 0.09)
    assert c.worst_level == NO_SMOOTHING
    # One fast frame is not enough to climb back.
    assert c.record(0.001, 0.1) == NO_SMOOTHING
    levels = drive(c, [0.01] * 100)  # now comfortably fast
    assert levels[-1] == FULL, "sustained headroom restores full quality"


def test_oscillating_workload_stays_put():
    """Load alternating around the threshold averages out and never moves.

    This is the real anti-flap guarantee: a window is a mean, so per-frame
    swings cannot produce a quality change.
    """
    c = QualityController(window=10, cooldown=20)
    noisy = [0.001 if i % 2 else 0.09 for i in range(400)]
    assert set(drive(c, noisy)) == {FULL}
    assert c.level == FULL


def test_hysteresis_and_cooldown_bound_change_rate():
    """Even a hard swinging workload changes level slowly, never every frame."""
    c = QualityController(window=10, cooldown=30)
    swing = ([0.09] * 40) * 6
    levels = drive(c, swing)
    changes = sum(1 for a, b in zip(levels, levels[1:]) if a != b)
    assert changes <= len(swing) // 30, "changes must be cooldown-separated"
    assert set(levels) <= {FULL, NO_SMOOTHING, MONOCHROME}


def test_max_level_clamps_ladder():
    """Half-block rendering needs color, so the ladder stops at NO_SMOOTHING."""
    c = QualityController(window=10, cooldown=20, max_level=NO_SMOOTHING)
    levels = drive(c, [0.09] * 500)
    assert set(levels) <= {FULL, NO_SMOOTHING}
    assert c.level == NO_SMOOTHING


def test_budget_must_be_positive():
    c = QualityController()
    with pytest.raises(ValueError):
        c.record(0.01, 0.0)


def test_invalid_construction_rejected():
    with pytest.raises(ValueError):
        QualityController(window=0)
    with pytest.raises(ValueError):
        QualityController(up=0.9, down=0.5)  # thresholds inverted
    with pytest.raises(ValueError):
        QualityController(window=10, cooldown=5)  # cooldown below one window


class _Fake:
    def __init__(self, enabled=True, color=True):
        self.enabled = enabled
        self.enable_color = color


def test_apply_level_is_reversible_and_idempotent():
    s, c = _Fake(), _Fake()
    levers = [(s, "enabled"), (c, "enable_color")]
    apply_level(FULL, levers)
    assert (s.enabled, c.enable_color) == (True, True), "level 0 changes nothing"

    apply_level(NO_SMOOTHING, levers)
    assert (s.enabled, c.enable_color) == (False, True)
    apply_level(NO_SMOOTHING, levers)
    assert (s.enabled, c.enable_color) == (False, True), "idempotent"

    apply_level(MONOCHROME, levers)
    assert (s.enabled, c.enable_color) == (False, False)

    apply_level(FULL, levers)
    assert (s.enabled, c.enable_color) == (True, True), "recovery restores base"


def test_apply_level_never_touches_a_lever_it_was_not_given():
    """Levers are discovered, so an unavailable one cannot be switched off.

    Half-block output needs color, so color is not offered as a lever there.
    A user who configured mono has no color lever either, so recovery must not
    silently re-enable color on their behalf.
    """
    s, c = _Fake(enabled=True, color=False), _Fake(enabled=False, color=False)
    apply_level(MONOCHROME, [(s, "enabled")])  # color deliberately not a lever
    assert (s.enabled, c.enable_color) == (False, False)
    apply_level(FULL, [(s, "enabled")])
    assert (s.enabled, c.enable_color) == (True, False), "must not re-enable color"


def test_empty_ladder_never_degrades():
    """With nothing optional to shed there is nothing to report degrading."""
    c = QualityController(window=10, cooldown=20, max_level=0)
    assert set(drive(c, [0.09] * 500)) == {FULL}
    assert (c.level, c.worst_level) == (FULL, FULL)


def test_level_stays_within_bounds_under_mixed_load():
    """Bounds hold for alternating up/down decisions, not just monotone ones."""
    c = QualityController(window=10, cooldown=20, max_level=MONOCHROME)
    mixed = ([0.09] * 40 + [0.001] * 40) * 8
    for level in drive(c, mixed):
        assert 0 <= level <= MONOCHROME
    assert c.worst_level <= MONOCHROME


def test_controller_is_deterministic_for_the_same_metric_sequence():
    """Two fresh controllers fed identical numbers produce identical traces."""
    script = [0.09 if (i // 90) % 2 else 0.001 for i in range(900)]
    first = drive(QualityController(), script)
    second = drive(QualityController(), script)
    assert first == second
    assert any(a != b for a, b in zip(first, first[1:])), "script must exercise it"


def test_cooldown_rounds_up_to_a_whole_window():
    """A cooldown that is not a multiple of the window is still honoured."""
    c = QualityController(window=10, cooldown=25)
    levels = drive(c, [0.09] * 300)
    first = levels.index(NO_SMOOTHING)
    second = levels.index(MONOCHROME)
    assert second - first >= 25, "the real gap can only exceed the cooldown"


def test_quality_name_tolerates_custom_ladders():
    """A level means 'levers shed', so a 1-lever ladder bottoms out at 1."""
    c = QualityController(window=10, cooldown=20, max_level=1)
    assert drive(c, [0.09] * 100)[-1] == 1
    assert c.worst_level == 1


# --------------------------------------------------------------------------
# Integration: the controller as actually wired into run()'s render loop.
# --------------------------------------------------------------------------

FRAME = bytes(range(256)) * 3  # 768 bytes = 16x16 RGB24


class _Clock:
    """Deterministic clock that only advances when something sleeps."""

    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class _SlowTerminal:
    """Terminal whose write_frame burns virtual time, simulating a heavy frame.

    Advancing the injected clock rather than really sleeping keeps the test
    instant and deterministic while still producing genuine per-frame work.
    """

    def __init__(self, clock, cost=0.0):
        self._clock = clock
        self._cost = cost
        self.frames = []

    def refresh_size(self):
        return False

    def output_size(self, _aspect):
        return 16, 16

    def write_frame(self, frame):
        self._clock.now()  # touch, keeps the fake honest
        self._clock.t += self._cost
        self.frames.append(frame)

    def clear(self):
        pass

    def restore(self):
        pass


class _Reader:
    def __init__(self, count, timestamps=None):
        self._n = count
        self.width = 16
        self.height = 16
        # Must exist even when None: run() reads it via getattr to decide
        # whether the source is variable-rate, so omitting the attribute would
        # silently force every adaptive test onto the fixed-FPS path.
        self.media_timestamps = timestamps

    def read_frame(self):
        if self._n <= 0:
            return None
        self._n -= 1
        return FRAME

    def close(self):
        pass


def _vfr_timestamps(n, step=0.2):
    """Source PTS at ``step`` seconds apart -- a deliberately slow variable-rate
    source, so each frame is given a 5x-nominal display slot."""
    return [i * step for i in range(n)]


def _drive_loop(n_frames, cost, adaptive, timestamps=None, clock_out=None, **cfg_kwargs):
    from src.config import Config
    from src.main import run
    from src.renderer import RGBAsciiRenderer
    from src.sync import PlaybackTimeline
    from src.timing import FrameClock

    clock = _Clock()
    fc = FrameClock(30, now=clock.now, sleep_fn=clock.sleep)
    terminal = _SlowTerminal(clock, cost)
    config = Config(fps=30, adaptive_quality=adaptive, **cfg_kwargs)
    result = run(
        _Reader(n_frames, timestamps), RGBAsciiRenderer(config), terminal, fc, config,
        None, PlaybackTimeline(playback_start=clock.t), media_duration=10.0,
    )
    if clock_out is not None:
        clock_out.append(fc)
    return result, terminal, config


def test_controller_sheds_quality_under_sustained_heavy_frames():
    """A stream that always overruns its budget must degrade, not fall behind."""
    # 50ms of work against a 33.3ms budget: sustained overload. Needs enough
    # presented frames to clear one window plus a cooldown per ladder step.
    result, terminal, config = _drive_loop(300, 0.05, True, enable_color=True)

    assert result == 0
    assert config.enable_color is False, "sustained overload sheds color"


def test_controller_does_not_alter_frame_scheduling():
    """Degrading quality changes what a frame looks like, never which frames run.

    Note the overloaded stream presents fewer than 120 frames either way: that
    is the pre-existing frame-drop path, which skips late frames rather than
    stretching the clock. Adaptive quality must be invisible to it.
    """
    heavy_on = _drive_loop(120, 0.05, True, enable_color=True)
    heavy_off = _drive_loop(120, 0.05, False, enable_color=True)

    assert len(heavy_on[1].frames) == len(heavy_off[1].frames)
    # The cheap run stays inside budget and is therefore left completely alone.
    light = _drive_loop(120, 0.0, True, enable_color=True)
    assert len(light[1].frames) == 120, "a stream inside budget drops nothing"
    assert light[2].enable_color is True


def test_adaptive_quality_off_leaves_config_untouched():
    """Opt-out gives byte-reproducible output regardless of machine speed."""
    result, terminal, config = _drive_loop(120, 0.05, False, enable_color=True)

    assert result == 0
    assert config.enable_color is True, "opt-out must never touch quality"
    assert all("\x1b[38;2;" in f for f in terminal.frames), "output stays colored"


def test_healthy_run_never_degrades():
    result, terminal, config = _drive_loop(120, 0.001, True, enable_color=True)

    assert len(terminal.frames) == 120
    assert config.enable_color is True, "a run inside budget is left alone"


def test_debug_report_runs_with_adaptive_quality(capsys):
    """The --debug report must survive a run it reports on.

    Regression: the quality line named a level->name table that did not exist,
    so every debug run raised NameError *after* a completely successful
    playback -- and, because the report runs before the audio-failure check,
    it also masked a genuine FFplay failure.
    """
    result, _, _ = _drive_loop(60, 0.001, True, enable_color=True, debug=True)

    assert result == 0
    err = capsys.readouterr().err
    assert "Quality level:   0 of 1" in err
    assert "Quality shed:    nothing" in err


def test_debug_report_names_what_it_actually_shed(capsys):
    """The worst-case level must also be reported, by lever not by table."""
    result, _, config = _drive_loop(
        300, 0.05, True, smoothing=0.3, debug=True
    )

    assert result == 0
    assert config.enable_color is False, "precondition: both levers shed"
    err = capsys.readouterr().err
    assert "Quality level:   2 of 2 (worst needed: 2)" in err
    assert "enabled, enable_color" in err


def test_variable_rate_source_keeps_color_when_frames_are_cheap():
    """A slow variable-rate source is mostly idle and must not be degraded.

    Regression: quality was charged against 1/fps (33ms) while the clock
    honoured source PTS. A 5fps source gives each frame a 200ms slot, so 50ms
    of work is 25% utilisation -- but it was reported as 150% and stripped to
    monochrome on a machine that was never overloaded.
    """
    stamps = _vfr_timestamps(300)
    result, terminal, config = _drive_loop(
        300, 0.05, True, timestamps=stamps, enable_color=True
    )

    assert result == 0
    assert config.enable_color is True, "cheap frames in a long slot are headroom"
    assert all("\x1b[38;2;" in f for f in terminal.frames)


def test_variable_rate_source_still_degrades_when_frames_really_overrun():
    """A longer slot must not become an excuse to never shed quality."""
    # 400ms of work against a 200ms slot: genuinely 200% utilised.
    result, _, config = _drive_loop(
        300, 0.4, True, timestamps=_vfr_timestamps(300), enable_color=True
    )

    assert result == 0
    assert config.enable_color is False, "real overload on VFR still sheds color"


def test_duplicate_timestamps_do_not_break_the_budget():
    """A duplicate source PTS creates no display interval.

    The chosen duplicate-PTS semantics say a repeated timestamp is valid input
    metadata but adds no display interval, so the slot between those two
    indices is zero. The controller must fall back to the nominal frame
    duration rather than dividing by zero or reading an infinite utilisation.
    """
    stamps = [0.0, 0.2, 0.2, 0.4, 0.4, 0.6]
    result, terminal, config = _drive_loop(
        6, 0.001, True, timestamps=stamps, enable_color=True
    )

    assert result == 0
    assert len(terminal.frames) > 0
    assert config.enable_color is True


def test_scheduling_is_identical_with_and_without_adaptive_quality():
    """Degrading quality must not move a single deadline or pacing decision."""
    # Each case needs a cost that overruns *its own* slot: a 33ms CFR frame and
    # a 200ms variable-rate frame are overloaded by very different amounts.
    cases = [(None, 0.05), (_vfr_timestamps(120), 0.25)]
    for stamps, cost in cases:
        on, off = [], []
        heavy_on = _drive_loop(120, cost, True, timestamps=stamps,
                               clock_out=on, enable_color=True)
        heavy_off = _drive_loop(120, cost, False, timestamps=stamps,
                                clock_out=off, enable_color=True)
        assert heavy_on[2].enable_color is False, "overload really did degrade"
        assert heavy_off[2].enable_color is True

        fast, slow = on[0], off[0]
        assert fast.report()["frame_count"] == slow.report()["frame_count"]
        assert fast.report()["late_frames"] == slow.report()["late_frames"]
        assert fast.report()["avg_pacing_ms"] == slow.report()["avg_pacing_ms"]
        assert fast.report()["avg_lateness_ms"] == slow.report()["avg_lateness_ms"]
        for index in (0, 1, 2, 5, 17):
            assert fast.deadline(index) == slow.deadline(index)


def test_half_block_mode_never_disables_color():
    """Half-block output encodes color in the glyph, so color is not optional.

    Regression: color used to be reachable by index in a fixed ladder, so
    half-block playback could ask the renderer for a mode that needs color
    while color was switched off. Color is now simply not offered as a lever.
    """
    result, terminal, config = _drive_loop(
        300, 0.05, True, enable_color=True, blocks=True
    )

    assert result == 0
    assert config.enable_color is True, "half-block rendering requires color"
    assert all("\u2580" in f for f in terminal.frames), "still rendering blocks"


def test_single_good_frame_never_upgrades_a_degraded_level():
    """Recovery needs a whole window of headroom, not one fast frame.

    Driven at the controller level so the lone fast frame lands in a *full*
    window of overload, which is the case that actually matters -- the existing
    recovery test only covers a fast frame arriving into an empty window, which
    merely exercises the partial-window early return.
    """
    controller = QualityController(window=10, cooldown=20, max_level=1)
    levels = drive(controller, [0.09] * 100 + [0.001] + [0.09] * 20)
    assert levels[-1] == 1, "one fast frame inside an overloaded stream changes nothing"

    # Only sustained low utilisation recovers.
    assert drive(controller, [0.001] * 200)[-1] == FULL


def test_sustained_headroom_restores_quality_after_overload():
    """Overload then a cheap stream: quality must come back."""
    from src.adaptive import apply_level
    from src.config import Config
    from src.smoothing import TemporalSmoother

    smoother = TemporalSmoother(Config(smoothing=0.3))
    levers = [(smoother, "enabled")]
    controller = QualityController(window=10, cooldown=20, max_level=1)
    levels = drive(controller, [0.09] * 100 + [0.001] * 200)

    apply_level(levels[-1], levers)
    assert smoother.enabled is True, "sustained headroom restores smoothing"
    assert levels[-1] == FULL
    assert controller.worst_level == NO_SMOOTHING, "worst level is remembered"


def test_disabling_smoothing_drops_its_history():
    """Shedding then restoring smoothing must not blend a stale ghost frame.

    Regression: the retained previous frame outlived a period of pass-through,
    so recovery blended against pre-downgrade content -- rendering stale pixels
    for several frames, which is the exact failure FrameSelector exists to
    prevent.
    """
    from src.config import Config
    from src.smoothing import TemporalSmoother

    smoother = TemporalSmoother(Config(smoothing=0.3))
    first = bytes([10] * 9)
    assert smoother.smooth(first) is first, "first frame initializes"

    darker = bytes([200] * 9)
    blended = smoother.smooth(darker)
    assert blended != bytes([200] * 9), "smoothing actually blended"

    smoother.enabled = False  # what adaptive level 1 does
    assert smoother.smooth(darker) is darker
    smoother.enabled = True

    # Recovery must start from what is on screen now, not from the old blend.
    assert smoother.smooth(darker) is darker, "no ghost of pre-downgrade content"
