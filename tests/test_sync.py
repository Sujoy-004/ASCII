"""Tests for Milestone 5: audio/video synchronization model.

No real subprocesses or media are used. Clocks, sleeps, and processes are
injected so the master-timeline, EOF, and completion policies are verified
deterministically.
"""

import subprocess
from unittest import mock

import pytest

from src.audio import AudioPlayer, detect_audio_status
from src.config import Config
from src.main import run
from src.renderer import RGBAsciiRenderer
from src.sync import (
    FLUSH_GRACE,
    AudioStatus,
    PlaybackTimeline,
    audio_completion_timeout,
    probe_media_duration,
    probe_video_size,
    probe_video_timestamps,
)
from src.timing import FrameClock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeProc:
    """Minimal subprocess.Popen stand-in."""

    def __init__(self, exited=False):
        self._exited = exited
        self.terminated = 0
        self.killed = 0

    def poll(self):
        return None if not self._exited else 0

    def terminate(self):
        self.terminated += 1
        self._exited = True

    def kill(self):
        self.killed += 1
        self._exited = True

    def wait(self, timeout=None):
        return 0


class TimedProc(FakeProc):
    """FakeProc that exits at a fake-clock time (simulates natural FFplay)."""

    def __init__(self, now, exited=False, exits_at=None):
        super().__init__(exited=exited)
        self._now = now
        self._exits_at = exits_at

    def poll(self):
        if self._exits_at is not None and self._now() >= self._exits_at:
            self._exited = True
        return None if not self._exited else 0


class FakeTime:
    """Deterministic fake clock recording sleeps (mirrors test_timing)."""

    def __init__(self, start=100.0):
        self.t = start
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


class FakeReader:
    def __init__(self, frames, width=4, height=4):
        self._frames = list(frames)
        self.width = width
        self.height = height
        self.closed = False

    def read_frame(self):
        if not self._frames:
            return None
        return self._frames.pop(0)

    def close(self):
        self.closed = True


class BoomReader(FakeReader):
    def read_frame(self):
        raise KeyboardInterrupt


class FakeTerminal:
    def __init__(self):
        self.written = 0
        self.restored = False

    def write_frame(self, _f):
        self.written += 1

    def restore(self):
        self.restored = True


def _black(width=4, height=4):
    return bytes(width * height * 3)


def _config(fps=1000):
    return Config(enable_color=False, fps=fps)


def _make_player(ffplay, ft, proc):
    with mock.patch("src.audio.subprocess.Popen", return_value=proc):
        player = AudioPlayer(ffplay=ffplay, now=ft.now, sleep_fn=ft.sleep)
        player.start("movie.mp4")
    player.launched_at = ft.t
    return player


def _build_run(timeline, audio, ft, media_duration=None, num_frames=2, fps=1000):
    config = _config(fps)
    reader = FakeReader([_black() for _ in range(num_frames)])
    terminal = FakeTerminal()
    clock = FrameClock(fps, now=ft.now, sleep_fn=ft.sleep)
    result = run(reader, RGBAsciiRenderer(config), terminal, clock, config,
                 audio, timeline, media_duration=media_duration)
    return result, reader, terminal


# ---------------------------------------------------------------------------
# A. Master playback start
# ---------------------------------------------------------------------------

def test_frameclock_can_be_seeded_at_playback_start():
    """The video clock accepts an external playback_start (shared timeline)."""
    ft = FakeTime(start=1000.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start(start_time=500.0)
    assert clock.start_time == 500.0
    assert clock.deadline(0) == 500.0
    assert clock.deadline(2) == pytest.approx(500.0 + 2 / 30)


def test_frameclock_default_start_uses_now():
    ft = FakeTime(start=777.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start()
    assert clock.start_time == 777.0


def test_timeline_offsets_share_playback_start():
    tl = PlaybackTimeline(
        playback_start=10.0,
        first_frame_at=10.300,
        audio_launched_at=10.020,
    )
    assert tl.video_startup_offset == pytest.approx(0.300)
    assert tl.audio_startup_offset == pytest.approx(0.020)


# ---------------------------------------------------------------------------
# B. Frame timeline / C. deadline stability
# ---------------------------------------------------------------------------

def test_frame_n_gets_presented_at_n_over_fps():
    ft = FakeTime(start=0.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start()
    for n in range(4):
        assert clock.deadline(n) == pytest.approx(n / 30)


def test_slow_frame_does_not_shift_later_deadlines():
    ft = FakeTime(start=0.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start()
    late_target = clock.deadline(5)  # absolute, fixed
    ft.t = 0.10  # frame 0 very late
    clock.wait_until(clock.deadline(0), proc_start=0.0)
    assert clock.deadline(5) == pytest.approx(late_target)  # unchanged


# ---------------------------------------------------------------------------
# D. Lateness: early / on-time / late
# ---------------------------------------------------------------------------

def test_lateness_recording_three_cases():
    ft = FakeTime(start=100.0)
    clock = FrameClock(30, now=ft.now, sleep_fn=ft.sleep)
    clock.start()
    d = clock.frame_duration

    # early (before deadline 100.0) -> sleeps to the deadline, not late
    ft.t = 100.0 - 0.010
    clock.wait_until(clock.deadline(0), proc_start=ft.t - 0.005)
    assert clock.stats.late_frames == 0

    # late by 40ms past deadline(1)
    ft.t = clock.deadline(1) + 0.040
    late = clock.wait_until(clock.deadline(1), proc_start=ft.t - 0.005)
    assert late == pytest.approx(0.040)
    assert clock.stats.late_frames == 1

    # sub-threshold lateness (1ms) for frame 2 is not a late frame
    ft.t = clock.deadline(2) + 0.001
    clock.wait_until(clock.deadline(2), proc_start=0.0)
    assert clock.stats.late_frames == 1
    assert clock.stats.on_time_frames == 2


# ---------------------------------------------------------------------------
# E. Startup offset measurement
# ---------------------------------------------------------------------------

def test_audio_player_records_launch_and_exit_timing():
    ft = FakeTime(start=50.0)
    proc = FakeProc(exited=False)
    player = _make_player("ffplay", ft, proc)
    assert player.launched_at == 50.0
    assert player.is_running() is True

    proc._exited = True  # natural exit
    assert player.is_running() is False
    assert player.exit_at == ft.t  # observed at current fake time


def test_audio_player_wait_for_exit_returns_when_exits():
    ft = FakeTime(start=0.0)
    proc = TimedProc(now=ft.now, exits_at=0.5)  # exits after 0.5s
    player = _make_player("ffplay", ft, proc)
    assert player.wait_for_exit(timeout=1.0) is True
    assert ft.t >= 0.5


def test_audio_player_wait_for_exit_times_out():
    ft = FakeTime(start=0.0)
    proc = TimedProc(now=ft.now, exits_at=None)  # never exits
    player = _make_player("ffplay", ft, proc)
    # timeout of 0.04s -> returns False without exiting
    assert player.wait_for_exit(timeout=0.04) is False


# ---------------------------------------------------------------------------
# F. Audio status tri-state
# ---------------------------------------------------------------------------

def test_audio_status_confirmed():
    result = mock.Mock()
    result.stdout = b"audio\n"
    with mock.patch("src.audio.subprocess.run", return_value=result):
        assert detect_audio_status("v.mp4", ffprobe="ffprobe") is AudioStatus.CONFIRMED


def test_audio_status_absent():
    result = mock.Mock()
    result.stdout = b""
    with mock.patch("src.audio.subprocess.run", return_value=result):
        assert detect_audio_status("v.mp4", ffprobe="ffprobe") is AudioStatus.ABSENT


def test_audio_status_unknown_when_ffprobe_missing():
    with mock.patch("src.audio.shutil.which", return_value=None):
        assert detect_audio_status("v.mp4") is AudioStatus.UNKNOWN


def test_audio_status_unknown_on_probe_error():
    with mock.patch("src.audio.subprocess.run", side_effect=OSError):
        assert detect_audio_status("v.mp4", ffprobe="ffprobe") is AudioStatus.UNKNOWN


def test_has_audio_stream_maps_to_tristate():
    import src.audio as A
    with mock.patch.object(A, "detect_audio_status") as d:
        d.return_value = AudioStatus.CONFIRMED
        assert A.has_audio_stream("v.mp4") is True
        d.return_value = AudioStatus.UNKNOWN
        assert A.has_audio_stream("v.mp4") is True
        d.return_value = AudioStatus.ABSENT
        assert A.has_audio_stream("v.mp4") is False


# ---------------------------------------------------------------------------
# G/H. EOF behavior + completion policy
# ---------------------------------------------------------------------------

def test_video_eof_while_audio_still_running_waits_for_natural_exit():
    """On normal EOF we must not force-kill audio that is legitimately still
    completing; we wait for it to exit naturally and only then clean up."""
    ft = FakeTime(start=0.0)
    proc = TimedProc(now=ft.now, exits_at=6.0)  # audio exits after EOF
    player = _make_player("ffplay", ft, proc)

    timeline = PlaybackTimeline(
        playback_start=0.0, audio_status=AudioStatus.CONFIRMED,
        audio_launched_at=0.0,
    )
    result, reader, terminal = _build_run(
        timeline, player, ft, media_duration=5.0,
    )
    assert result == 0
    assert proc.terminated == 0            # not force-terminated
    assert timeline.audio_waited_for_exit is True
    assert timeline.completion_offset is not None
    assert reader.closed and terminal.restored


def test_video_eof_after_audio_already_exited_skips_wait():
    """If audio already exited before video EOF, no wait/terminate occurs."""
    ft = FakeTime(start=0.0)
    proc = FakeProc(exited=True)
    player = _make_player("ffplay", ft, proc)
    player.exit_at = 1.0

    timeline = PlaybackTimeline(
        playback_start=0.0, audio_status=AudioStatus.CONFIRMED,
        audio_launched_at=0.0, audio_exit_at=1.0,
    )
    result, reader, terminal = _build_run(timeline, player, ft)
    assert result == 0
    assert proc.terminated == 0                        # nothing to stop
    assert timeline.audio_waited_for_exit is False     # wasn't running at EOF


def test_completion_policy_force_stops_if_audio_never_exits():
    """FFplay must eventually be cleaned up even if it never exits."""
    ft = FakeTime(start=0.0)
    proc = TimedProc(now=ft.now, exits_at=None)  # never exits
    player = _make_player("ffplay", ft, proc)

    timeline = PlaybackTimeline(
        playback_start=0.0, audio_status=AudioStatus.CONFIRMED,
        audio_launched_at=0.0,
    )
    result, reader, terminal = _build_run(
        timeline, player, ft, media_duration=5.0,
    )
    assert result == 0
    assert proc.terminated == 1                # safety-net forced stop
    assert timeline.audio_waited_for_exit is True


def test_interrupt_stops_audio_immediately():
    """Ctrl+C must stop audio without waiting for natural exit."""
    ft = FakeTime(start=0.0)
    proc = FakeProc(exited=False)
    player = _make_player("ffplay", ft, proc)

    timeline = PlaybackTimeline(
        playback_start=0.0, audio_status=AudioStatus.CONFIRMED,
        audio_launched_at=0.0,
    )
    config = _config()
    clock = FrameClock(1000, now=ft.now, sleep_fn=ft.sleep)
    result = run(BoomReader([]), RGBAsciiRenderer(config), FakeTerminal(),
                 clock, config, player, timeline, media_duration=5.0)
    assert result == 0
    assert proc.terminated == 1                          # stopped immediately
    assert timeline.audio_waited_for_exit is False       # skipped the wait


def test_audio_absent_no_wait_no_stop():
    """No audio stream -> nothing to wait for or stop."""
    ft = FakeTime(start=0.0)
    timeline = PlaybackTimeline(playback_start=0.0, audio_status=AudioStatus.ABSENT)
    result, reader, terminal = _build_run(timeline, None, ft)
    assert result == 0
    assert reader.closed and terminal.restored
    assert timeline.audio_waited_for_exit is False


def test_run_audio_without_timeline_is_safe():
    """Defensive: audio present but no timeline must not raise on cleanup."""
    ft = FakeTime(start=0.0)
    proc = FakeProc(exited=True)  # already exited -> no wait, no terminate
    player = _make_player("ffplay", ft, proc)

    config = _config()
    clock = FrameClock(1000, now=ft.now, sleep_fn=ft.sleep)
    reader = FakeReader([_black()])
    terminal = FakeTerminal()
    result = run(reader, RGBAsciiRenderer(config), terminal, clock, config,
                 player, None, media_duration=5.0)
    assert result == 0
    assert proc.terminated == 0
    assert terminal.restored


# ---------------------------------------------------------------------------
# Media duration probing
# ---------------------------------------------------------------------------

def test_probe_media_duration_parses():
    result = mock.Mock()
    result.stdout = b"5.000000\n"
    with mock.patch("src.audio.subprocess.run", return_value=result), \
         mock.patch("src.audio.shutil.which", return_value="ffprobe"):
        assert probe_media_duration("v.mp4") == pytest.approx(5.0)


def test_probe_media_duration_failsafe_none():
    with mock.patch("src.audio.shutil.which", return_value=None):
        assert probe_media_duration("v.mp4") is None


def test_probe_video_size_parses():
    result = mock.Mock()
    result.stdout = b"1920x1080\n"
    with mock.patch("src.audio.subprocess.run", return_value=result), \
         mock.patch("src.audio.shutil.which", return_value="ffprobe"):
        assert probe_video_size("v.mp4") == (1920, 1080)


def test_probe_video_size_failsafe_none_when_ffprobe_missing():
    with mock.patch("src.audio.shutil.which", return_value=None):
        assert probe_video_size("v.mp4") is None


def test_probe_video_size_failsafe_none_on_bad_output():
    result = mock.Mock()
    result.stdout = b"not-a-size\n"
    with mock.patch("src.audio.subprocess.run", return_value=result), \
         mock.patch("src.audio.shutil.which", return_value="ffprobe"):
        assert probe_video_size("v.mp4") is None


def test_audio_completion_timeout_timeline_based():
    # At video EOF now≈start+duration -> ~FLUSH_GRACE remains (no hard delay).
    to = audio_completion_timeout(0.0, 5.0, media_duration=5.0)
    assert to == pytest.approx(FLUSH_GRACE)
    # Early (audio just started): full remaining duration + grace.
    to2 = audio_completion_timeout(0.0, 0.5, media_duration=5.0)
    assert to2 == pytest.approx(FLUSH_GRACE + 4.5)
    # Unknown duration -> grace bound only.
    assert audio_completion_timeout(0.0, 5.0, None) == pytest.approx(FLUSH_GRACE)



def test_probe_video_timestamps_normalizes_and_preserves_vfr():
    result = mock.Mock()
    result.stdout = b"10.000000\n10.040000\n10.080000\n10.140000\n"
    with mock.patch("src.sync.subprocess.run", return_value=result), \
         mock.patch("src.sync.shutil.which", return_value="ffprobe"):
        assert probe_video_timestamps("v.mp4") == pytest.approx(
            (0.0, 0.04, 0.08, 0.14)
        )


def test_probe_video_timestamps_failsafe_none():
    result = mock.Mock()
    result.stdout = b"N/A\n"
    with mock.patch("src.sync.subprocess.run", return_value=result), \
         mock.patch("src.sync.shutil.which", return_value="ffprobe"):
        assert probe_video_timestamps("v.mp4") is None
