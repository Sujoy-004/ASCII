"""RGB ASCII & Retro FX Studio - Core Media Engine.

High-performance, zero-dependency media transformation core providing Rec. 601
luminance mapping, ASCII and ANSI True Color formatting, area-averaging frame
rescaling, and FFmpeg streaming subprocess pipelines.
"""

from __future__ import annotations

from src.adaptive import QualityController, apply_level
from src.audio import (
    AudioPlayer,
    FFplayNotFoundError,
    FFplayPlaybackError,
    detect_audio_status,
    has_audio_stream,
)
from src.config import CHAR_PRESETS, DEFAULT_CHARS, Config
from src.framesel import DropStats, FrameSelector
from src.renderer import (
    RGBAsciiRenderer,
    ansi_truecolor,
    char_for_brightness,
    char_table_for,
    frame_size,
    luminance,
    pixel_index,
    resize_rgb24,
    resize_rgb24_area,
)
from src.smoothing import TemporalSmoother
from src.sync import (
    AudioStatus,
    PlaybackTimeline,
    TimestampStream,
    audio_completion_timeout,
    probe_media_duration,
    probe_video_rate,
    probe_video_size,
)
from src.timing import FrameClock, TimestampSource
from src.video import (
    FFmpegDecodeError,
    FFmpegFrameReader,
    FFmpegNotFoundError,
    ScaleDim,
    classify_decode_termination,
)

__all__ = [
    # Renderer & Algorithms
    "RGBAsciiRenderer",
    "luminance",
    "char_table_for",
    "char_for_brightness",
    "ansi_truecolor",
    "pixel_index",
    "frame_size",
    "resize_rgb24",
    "resize_rgb24_area",
    # Configuration
    "Config",
    "DEFAULT_CHARS",
    "CHAR_PRESETS",
    # Video & Audio Decoding Subprocesses
    "FFmpegFrameReader",
    "ScaleDim",
    "classify_decode_termination",
    "FFmpegNotFoundError",
    "FFmpegDecodeError",
    "AudioPlayer",
    "detect_audio_status",
    "has_audio_stream",
    "FFplayNotFoundError",
    "FFplayPlaybackError",
    # Timeline, Timing & Sync
    "PlaybackTimeline",
    "AudioStatus",
    "TimestampStream",
    "audio_completion_timeout",
    "probe_media_duration",
    "probe_video_rate",
    "probe_video_size",
    "FrameClock",
    "TimestampSource",
    # Pacing, Selection & Adaptation
    "FrameSelector",
    "DropStats",
    "TemporalSmoother",
    "QualityController",
    "apply_level",
]
