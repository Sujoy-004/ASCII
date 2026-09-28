"""Playback synchronization: a shared master timeline and A/V timing model.

Keeps the three temporal notions the rest of the system must keep distinct:

- wall/process time  -- raw monotonic seconds (time.perf_counter)
- video presentation time -- driven by FrameClock absolute deadlines
- audio playback time -- observed from FFplay's reported audio-master media clock

This module owns the single shared ``playback_start`` reference, the per
subsystem timing observations, audio-status tri-state, and the
end-of-playback completion policy. It does not launch processes or render
video.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import Enum


class AudioStatus(Enum):
    """Tri-state result of audio-stream detection."""

    CONFIRMED = "CONFIRMED"  # ffprobe positively found >=1 audio stream
    ABSENT = "ABSENT"        # ffprobe positively found no audio stream
    UNKNOWN = "UNKNOWN"      # ffprobe unavailable or probing failed


@dataclass
class PlaybackTimeline:
    """Observations along the single shared playback timeline.

    All timestamps are monotonic seconds on the same clock as
    ``playback_start`` (time.perf_counter by default).
    """

    playback_start: float
    # --- video ---
    video_launched_at: float | None = None
    first_frame_at: float | None = None
    video_eof_at: float | None = None
    frame_count: int = 0
    # --- audio ---
    audio_status: AudioStatus = AudioStatus.ABSENT
    audio_launched_at: float | None = None
    audio_exit_at: float | None = None
    last_av_drift: float | None = None
    max_av_drift: float = 0.0
    # --- completion ---
    audio_waited_for_exit: bool = False

    @property
    def video_startup_offset(self) -> float | None:
        """Delay from playback start to the first presented frame."""
        if self.first_frame_at is None:
            return None
        return self.first_frame_at - self.playback_start

    @property
    def audio_startup_offset(self) -> float | None:
        """Delay from playback start to the FFplay process launch."""
        if self.audio_launched_at is None:
            return None
        return self.audio_launched_at - self.playback_start

    @property
    def completion_offset(self) -> float | None:
        """Time from video EOF to audio natural exit (the audible tail)."""
        if self.video_eof_at is None or self.audio_exit_at is None:
            return None
        return self.audio_exit_at - self.video_eof_at


# Safety ceiling (seconds) for the natural-exit wait, covering FFplay's
# process startup plus its decoder/flush after the file is consumed.
#
# This is NOT a presentational delay inserted at EOF. It is an upper bound
# only: FFplay normally exits on its own well inside it (the pre-M5 audit
# measured a ~0.25-0.86s tail beyond video EOF). It prevents waiting forever
# on a hung external process.
FLUSH_GRACE = 2.0


# Constant-frame-rate detection tolerances (see probe_video_rate). A source is
# only trusted as CFR when its own r_frame_rate and avg_frame_rate agree to
# within this relative difference AND the header's frame/duration counts match
# that rate; otherwise it is treated as variable rate and given the streaming
# timestamp probe instead. Deliberately strict: trusting a wrong rate would
# pace the whole video on the grid, so uncertainty goes to the streaming path,
# which degrades toward the fixed-FPS fallback on its own.
RATE_REL_EQ = 1e-6
RATE_MIN = 1.0
RATE_MAX = 240.0
FRAME_COUNT_TOLERANCE = 2.0


def audio_completion_timeout(
    audio_started_at: float,
    now: float,
    media_duration: float | None,
) -> float:
    """Timeline-based upper bound (seconds) to wait for FFplay natural exit.

    Derived from when audio was launched and the media length, so it is not a
    fixed empirical delay. At video EOF ``now`` is typically near
    ``audio_started_at + media_duration``, leaving roughly ``FLUSH_GRACE`` for
    the residual buffered/flush tail. If the duration is unknown (cannot be
    probed), the grace bound alone is used.
    """
    if media_duration is not None:
        return max(0.0, (audio_started_at + media_duration + FLUSH_GRACE) - now)
    return FLUSH_GRACE


def probe_media_duration(
    video_path: str,
    ffprobe: str | None = None,
) -> float | None:
    """Return the container duration (seconds) via FFprobe.

    Returns None if FFprobe is unavailable, the probe fails, or the value
    cannot be parsed. Callers must treat None as "unknown".
    """
    ffprobe = ffprobe or shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # A non-zero status means the probe failed even if it managed to print
        # something parsable (a truncated or partially readable container, for
        # example). Trusting that output would hand the caller a duration that
        # does not describe the file.
        if result.returncode != 0:
            return None
        text = result.stdout.decode(errors="replace").strip()
        if not text:
            return None
        return float(text)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _trusted_timeline(
    values: list[float], duration: float | None
) -> tuple[float, ...] | None:
    """Normalize raw presentation timestamps, or reject the whole timeline.

    FFprobe emits one row per decoded frame, so the list indexes frames
    positionally. Rejecting the entire timeline (rather than dropping a bad
    entry) is what keeps the list aligned with frame indexes: a skipped entry
    would shift every later frame onto a neighbour's timestamp.

    ``None`` means the caller must use fixed-FPS timing for the whole video.
    """
    if any(not math.isfinite(value) for value in values):
        return None
    # Ordering is checked on the raw values, before normalization, so an
    # out-of-order timestamp cannot hide behind the subtraction.
    if any(after < before for before, after in zip(values, values[1:])):
        return None
    normalized = tuple(value - values[0] for value in values)
    if duration is not None and duration > 0:
        # The last frame belongs near the end of the media. A timeline that
        # ends far earlier describes only part of the file, so trusting it
        # would pace the whole video against a fraction of its real length.
        slack = max(1.0, duration * 0.1)
        if normalized[-1] + slack < duration * 0.9:
            return None
    return normalized


def probe_video_timestamps(
    video_path: str,
    ffprobe: str | None = None,
    duration: float | None = None,
) -> tuple[float, ...] | None:
    """Return normalized video frame timestamps in presentation order.

    FFprobe's best-effort timestamps reflect the decoded video timeline and
    preserve variable frame durations when the source has them. The result is
    normalized so the first timestamp is media time zero. ``None`` means the
    timestamps could not be trusted as a frame-indexed timeline; callers then
    use their fixed-FPS fallback. ``duration`` is the media duration, used to
    reject a timeline that plainly does not describe the same file.
    """
    ffprobe = ffprobe or shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "frame=best_effort_timestamp_time",
                "-of", "csv=p=0",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return None
        values: list[float] = []
        for raw in result.stdout.decode(errors="replace").splitlines():
            text = raw.split(",", 1)[0].strip()
            if not text or text.upper() == "N/A":
                # A row without a value means the remaining timestamps no
                # longer line up with the frame indexes they would be read by.
                return None
            try:
                values.append(float(text))
            except ValueError:
                return None
        if not values:
            return None
        return _trusted_timeline(values, duration)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def probe_video_size(video_path: str, ffprobe: str | None = None) -> tuple[int, int] | None:
    """Return the source video's (width, height) in pixels via FFprobe.

    Returns None if FFprobe is unavailable, the probe fails, or the values
    cannot be parsed. Callers must treat None as "unknown" and fall back to a
    sensible aspect-ratio default.
    """
    ffprobe = ffprobe or shutil.which("ffprobe")
    if ffprobe is None:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0:s=x",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # As in probe_media_duration: a failed probe's output is not evidence,
        # even when it happens to be parsable. A wrong source size would feed
        # a wrong aspect ratio into the terminal grid calculation.
        if result.returncode != 0:
            return None
        text = result.stdout.decode(errors="replace").strip()
        if not text or "x" not in text:
            return None
        w, h = text.split("x", 1)
        width = int(w)
        height = int(h)
        if width <= 0 or height <= 0:
            return None
        return width, height
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _parse_int(text: str | None) -> int | None:
    """Parse an integer ffprobe field, or None when absent or malformed."""
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_float(text: str | None) -> float | None:
    """Parse a float ffprobe field, or None when absent or malformed."""
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def probe_video_rate(
    video_path: str,
    ffprobe: str | None = None,
) -> tuple[float | None, bool]:
    """Return the frame rate when the source is constant-frame-rate (CFR).

    Returns ``(rate, True)`` when the source is positively determined to be
    CFR, ``(None, False)`` otherwise. A CFR source can pace on the fixed grid
    (``1/rate``) immediately, skipping the full-file timestamp enumeration that
    used to gate every playback start; only a variable-rate source needs the
    streaming timestamp probe.

    The check is deliberately strict. ffprobe's header alone can claim a rate
    on a variable-rate file (some VFR containers report equal
    r_frame_rate/avg_frame_rate while printing N/A for the frame/duration
    counts), so CFR is only declared when:

    - r_frame_rate and avg_frame_rate both parse, are finite and positive,
      within [RATE_MIN, RATE_MAX], and agree to within ``RATE_REL_EQ``
      (relative);
    - nb_frames and duration are both present and positive, and the frame
      count matches ``duration * rate`` within ``FRAME_COUNT_TOLERANCE``.

    Any missing or inconsistent field means NOT CFR. ``-of default=nw=1`` is
    used deliberately: with ``csv=p=0`` ffprobe emits stream fields in AVStream
    struct order rather than the requested order, so field names cannot be
    trusted there.
    """
    ffprobe = ffprobe or shutil.which("ffprobe")
    if ffprobe is None:
        return None, False
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries",
                "stream=r_frame_rate,avg_frame_rate,nb_frames,duration",
                "-of", "default=nw=1",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return None, False
        fields: dict[str, str] = {}
        for line in result.stdout.decode(errors="replace").splitlines():
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()

        def _rate(field: str) -> float | None:
            text = fields.get(field)
            if text and "/" in text:
                num_s, _, den_s = text.partition("/")
                num, den = _parse_float(num_s), _parse_float(den_s)
                if num is None or den is None or den == 0:
                    return None
                return num / den
            value = _parse_float(text)
            if value is None or not math.isfinite(value) or value <= 0:
                return None
            return value

        r_rate, avg_rate = _rate("r_frame_rate"), _rate("avg_frame_rate")
        if r_rate is None or avg_rate is None:
            return None, False
        if abs(r_rate - avg_rate) > RATE_REL_EQ * max(r_rate, avg_rate):
            return None, False
        if not RATE_MIN <= r_rate <= RATE_MAX:
            return None, False
        nb_frames = _parse_int(fields.get("nb_frames"))
        duration = _parse_float(fields.get("duration"))
        if nb_frames is None or nb_frames <= 0:
            return None, False
        if duration is None or duration <= 0:
            return None, False
        if abs(nb_frames - duration * r_rate) > FRAME_COUNT_TOLERANCE:
            return None, False
        return r_rate, True
    except (OSError, subprocess.SubprocessError, ValueError):
        return None, False


def _timestamp_probe_cmd(
    video_path: str, ffprobe: str | None
) -> list[str] | None:
    """The ffprobe command TimestampStream runs, or None if FFprobe is
    unavailable. The same enumeration and output format
    ``probe_video_timestamps`` uses, so a stream and a fully probed tuple
    describe the same timeline."""
    ffprobe = ffprobe or shutil.which("ffprobe")
    if ffprobe is None:
        return None
    return [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "frame=best_effort_timestamp_time",
        "-of", "csv=p=0",
        video_path,
    ]


class TimestampStream:
    """Streaming producer of normalized video frame presentation timestamps.

    Runs the same ffprobe frame-enumeration command as
    ``probe_video_timestamps``, but as a long-lived subprocess read
    incrementally on a daemon thread, so playback can begin on the prefix
    already decoded instead of blocking until the whole timeline exists.
    Startup latency for a variable-rate source therefore stays bounded:

    - the probe is launched before the decoder warms up and reads one row per
      frame as ffprobe decodes them (several times real time);
    - ``at()`` never blocks: it answers from the prefix validated so far using
      the same three-branch frame-index-to-media-time model as
      ``FrameClock.target_media_time`` (the value at the index, the source's
      own final inter-frame gap extended past the prefix, or the fixed-FPS
      grid when fewer than two values exist);
    - rows are validated progressively, and a bad row poisons the stream at
      that index without disturbing the usable prefix, so later frames never
      shift onto a neighbour's timestamp.

    ``close()`` is idempotent and never raises, so it can run from ``finally``
    blocks both inside and outside the playback loop.

    Unlike the legacy ``_trusted_timeline`` guard (used by
    ``probe_video_timestamps``), the stream
    never compares a short prefix against the media duration: a truncated
    source ends playback at the decoder's own EOF, which lands exactly at the
    prefix's last index, so the extrapolation that the guard protects is
    unreachable. A duration-guarded equivalent would only freeze the stream
    onto its fixed-FPS fallback, which paces a variable-rate source far worse
    (measured ~3x the mean error) than trusting the local cadence.
    """

    def __init__(
        self,
        video_path: str,
        frame_duration: float,
        ffprobe: str | None = None,
    ) -> None:
        self.video_path = video_path
        self.frame_duration = frame_duration
        self.ffprobe = ffprobe or shutil.which("ffprobe")
        self._proc: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # Normalized prefix, index-aligned with the frames read so far; the
        # first raw value is subtracted, so a negative source start is
        # preserved exactly as probe_video_timestamps  would.
        self._values: list[float] = []
        self._poisoned = False

    def start(self) -> bool:
        """Launch the FFprobe subprocess and its reader thread.

        Returns False when FFprobe is unavailable or cannot be launched (the
        caller then keeps the fixed-FPS schedule). Idempotent: once started
        the stream keeps running until ``close()``.
        """
        cmd = _timestamp_probe_cmd(self.video_path, self.ffprobe)
        if cmd is None:
            return False
        if self._proc is not None:
            return True
        try:
            stderr_tmp = tempfile.TemporaryFile()
        except OSError:
            return False
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=stderr_tmp,
            )
        except OSError:
            stderr_tmp.close()
            return False
        if proc.stdout is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (OSError, subprocess.SubprocessError):
                pass
            stderr_tmp.close()
            return False
        self._proc = proc
        self._thread = threading.Thread(
            target=self._read,
            args=(proc.stdout,),
            name="timestamp-probe",
            daemon=True,
        )
        self._thread.start()
        return True

    def _read(self, stream) -> None:
        """Reader thread: parse ffprobe rows into the validated prefix."""
        pending = b""
        read1 = getattr(stream, "read1", stream.read)
        raw: list[float] = []
        try:
            while True:
                chunk = read1(65536)
                if not chunk:
                    break
                pending += chunk
                parts = pending.split(b"\n")
                pending = parts.pop()
                for part in parts:
                    if not self._append(raw, part):
                        return
            if pending:
                self._append(raw, pending)
        except (OSError, ValueError):
            pass

    def _append(self, raw: list[float], line: bytes) -> bool:
        """Validate one ffprobe row and add it to the prefix.

        Returns False on the first unusable or non-increasing row, poisoning
        the stream: further rows stop being published, but the prefix already
        published stays valid.
        """
        text = line.decode(errors="replace").split(",", 1)[0].strip()
        if not text or text.upper() == "N/A":
            return self._poison()
        try:
            value = float(text)
        except ValueError:
            return self._poison()
        if not math.isfinite(value) or (raw and value < raw[-1]):
            return self._poison()
        raw.append(value)
        normalized = value - raw[0]
        with self._lock:
            self._values.append(normalized)
        return True

    def _poison(self) -> bool:
        with self._lock:
            self._poisoned = True
        return False

    @property
    def poisoned(self) -> bool:
        """True once a later row was unusable or out of order."""
        with self._lock:
            return self._poisoned

    def at(self, frame_index: int) -> float:
        """Media time for ``frame_index`` from the prefix read so far.

        Never blocks and never raises: with no data at all it falls back to
        the fixed-FPS grid answer, so a consumer can always call it and its
        answer is exactly what ``FrameClock.target_media_time`` would give for
        the same validated prefix.
        """
        with self._lock:
            n = len(self._values)
            if 0 <= frame_index < n:
                return self._values[frame_index]
            if frame_index >= n >= 2:
                gap = self._values[-1] - self._values[-2]
                return self._values[-1] + (frame_index - n + 1) * gap
        return frame_index * self.frame_duration

    def wait_ready(self, min_values: int = 2, timeout: float = 0.25) -> bool:
        """Wait up to ``timeout`` for ``min_values`` validated rows.

        Polls rather than blocking on an event so a probe that died early is
        detected immediately. Only bounds the tail: the common case returns
        the moment the rows land. Never blocks past ``timeout``.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            with self._lock:
                if len(self._values) >= min_values:
                    return True
                thread = self._thread
            if thread is None or not thread.is_alive():
                return False
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.005)

    def close(self) -> None:
        """Terminate the probe and release its resources. Never raises.

        Runs from ``finally`` blocks in both the playback loop and main(), so
        every step degrades to a no-op: a never-started stream, an
        already-closed stream, and a process that refuses to exit are all
        handled, and a second call is safe.
        """
        proc, self._proc = self._proc, None
        thread, self._thread = self._thread, None
        if proc is not None:
            try:
                if proc.poll() is None:
                    try:
                        proc.terminate()
                    except OSError:
                        pass
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        try:
                            proc.kill()
                        except OSError:
                            pass
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            pass
            except OSError:
                pass
        if thread is not None:
            try:
                thread.join(timeout=0.5)
            except (OSError, RuntimeError):
                pass
        for stream in (
            getattr(proc, "stdout", None),
            getattr(proc, "stderr", None),
        ):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
