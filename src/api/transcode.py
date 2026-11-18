"""Low-memory FFmpeg video and animated GIF transcoding engine with live telemetry."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable

from src.api.config import config
from src.api.jobs import ExportJob

logger = logging.getLogger(__name__)


def validate_assembled_media(
    input_path: str,
    format: str,
    max_duration: float | None = None,
) -> dict[str, object]:
    """Inspect assembled container with ffprobe before admitting to transcode per D-07."""
    if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
        raise ValueError(f"Input media file '{input_path}' is empty or does not exist.")

    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        raise RuntimeError("ffprobe executable not found on system PATH.")

    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration,r_frame_rate:format=duration",
        "-of",
        "json",
        input_path,
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10.0)
        data = json.loads(res.stdout)
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"Corrupt media container or invalid video stream: {exc.stderr.strip()}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to probe media file: {exc}") from exc

    streams = data.get("streams", [])
    if not streams:
        raise ValueError("No video stream found in uploaded media.")

    video_info = streams[0]
    width = int(video_info.get("width", 0))
    height = int(video_info.get("height", 0))

    # Duration resolution: prefer format duration, fallback to stream duration
    duration = 0.0
    fmt_info = data.get("format", {})
    if fmt_info.get("duration"):
        try:
            duration = float(fmt_info["duration"])
        except (ValueError, TypeError):
            duration = 0.0
    if duration == 0.0 and video_info.get("duration"):
        try:
            duration = float(video_info["duration"])
        except (ValueError, TypeError):
            duration = 0.0

    # Max duration check per D-07
    limit = max_duration or (config.max_gif_duration if format == "gif" else config.max_video_duration)
    if duration > limit + 1.0:  # Allow 1s tolerance for container timestamps
        raise ValueError(
            f"Media duration ({duration:.2f}s) exceeds maximum allowed {limit:.1f}s for format '{format}'."
        )

    # Resolution ceilings per D-07
    if format == "gif":
        if width > 1280 or height > 720:
            raise ValueError(f"GIF resolution {width}x{height} exceeds 720p limit (1280x720).")
    else:
        if width > 1920 or height > 1080:
            raise ValueError(f"Video resolution {width}x{height} exceeds 1080p limit (1920x1080).")

    return {
        "width": width,
        "height": height,
        "duration": duration,
        "format": format,
    }


def parse_progress_line(line: str) -> dict[str, str]:
    """Parse a single key=value line from FFmpeg -progress pipe:1 per D-03."""
    if "=" not in line:
        return {}
    key, val = line.strip().split("=", 1)
    return {key.strip(): val.strip()}


def build_mp4_transcode_command(
    input_path: str,
    output_path: str,
    source_audio_path: str | None = None,
    clip_start: float = 0.0,
    clip_duration: float = 0.0,
) -> list[str]:
    """Build FFmpeg command enforcing -threads 1, ultrafast preset, and optional audio fallback per D-01, D-05, D-07."""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    cmd: list[str] = [ffmpeg_bin, "-y"]

    if source_audio_path and os.path.exists(source_audio_path):
        # Pre-input seeking for pristine source audio fallback per D-05
        if clip_start > 0:
            cmd.extend(["-ss", f"{clip_start:.3f}"])
        if clip_duration > 0:
            cmd.extend(["-t", f"{clip_duration:.3f}"])
        cmd.extend(["-i", source_audio_path])
        cmd.extend(["-i", input_path])
        # Map video from assembled canvas (input 1) and audio from source (input 0)
        cmd.extend(["-map", "1:v:0", "-map", "0:a:0?"])
        cmd.extend(["-af", "aresample=async=1:first_pts=0", "-shortest"])
    else:
        cmd.extend(["-i", input_path])

    # Enforce -threads 1 and ultrafast preset to guarantee RSS < 200 MB per D-07
    cmd.extend([
        "-threads",
        "1",
        "-preset",
        "ultrafast",
        "-c:v",
        "libx264",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-progress",
        "pipe:1",
        output_path,
    ])

    return cmd


def build_gif_transcode_commands(
    input_path: str,
    output_path: str,
    palette_path: str,
    fps: int = 12,
) -> tuple[list[str], list[str]]:
    """Build two-pass memory-optimized GIF transcoding commands keeping peak RSS < 70 MB per D-07."""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

    # Pass 1: generate 128-color palette to disk
    pass1_cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        input_path,
        "-vf",
        f"fps={fps},palettegen=max_colors=128",
        "-threads",
        "1",
        "-an",
        palette_path,
    ]

    # Pass 2: apply palette with Bayer ordered dithering
    pass2_cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        input_path,
        "-i",
        palette_path,
        "-lavfi",
        f"fps={fps}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
        "-threads",
        "1",
        "-an",
        "-progress",
        "pipe:1",
        output_path,
    ]

    return pass1_cmd, pass2_cmd


def mux_fallback_audio(
    source_path: str,
    canvas_video_path: str,
    output_path: str,
    start_sec: float = 0.0,
    duration_sec: float = 0.0,
) -> list[str]:
    """Build pre-input seeking command for source audio muxing per D-05."""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg_bin, "-y"]
    if start_sec > 0:
        cmd.extend(["-ss", f"{start_sec:.3f}"])
    if duration_sec > 0:
        cmd.extend(["-t", f"{duration_sec:.3f}"])
    cmd.extend([
        "-i",
        source_path,
        "-i",
        canvas_video_path,
        "-map",
        "1:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-af",
        "aresample=async=1:first_pts=0",
        "-shortest",
        output_path,
    ])
    return cmd


async def run_ffmpeg_transcode(
    job: ExportJob,
    input_path: str,
    output_path: str,
    on_progress: Callable[[float, float, str], None] | None = None,
) -> str:
    """Execute memory-bounded video or animated GIF transcoding asynchronously per D-01, D-02, D-07."""
    target_duration_us = int(max(1.0, job.duration) * 1_000_000)

    if job.format == "gif":
        palette_path = str(Path(input_path).parent / "palette.png")
        fps = min(15, max(8, job.fps or 12))
        pass1_cmd, pass2_cmd = build_gif_transcode_commands(
            input_path=input_path,
            output_path=output_path,
            palette_path=palette_path,
            fps=fps,
        )

        # Execute Pass 1 (Palette generation)
        proc1 = await asyncio.create_subprocess_exec(
            *pass1_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        job.pid = proc1.pid
        stdout1, stderr1 = await proc1.communicate()
        if proc1.returncode != 0:
            raise RuntimeError(f"GIF palette generation failed: {stderr1.decode('utf-8', errors='replace')}")

        # Execute Pass 2 (Palette application with progress)
        proc2 = await asyncio.create_subprocess_exec(
            *pass2_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        job.pid = proc2.pid

        # Parse live progress from pipe:1 stdout
        current_fps = 0.0
        current_speed = "1.0x"
        if proc2.stdout:
            while True:
                line_bytes = await proc2.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key == "fps":
                        try:
                            current_fps = float(val)
                        except ValueError:
                            pass
                    elif key == "speed":
                        current_speed = val
                    elif key == "out_time_us":
                        try:
                            out_us = int(val)
                            pct = min(0.99, max(0.0, out_us / target_duration_us))
                            job.progress = pct
                            if on_progress:
                                on_progress(pct, current_fps, current_speed)
                        except ValueError:
                            pass

        await proc2.wait()
        job.pid = None
        if proc2.returncode != 0:
            stderr2 = await proc2.stderr.read() if proc2.stderr else b""
            raise RuntimeError(f"GIF transcode failed: {stderr2.decode('utf-8', errors='replace')}")

        # Clean up intermediate palette
        if os.path.exists(palette_path):
            try:
                os.unlink(palette_path)
            except OSError:
                pass

    else:
        # MP4 H.264 transcode with -threads 1
        cmd = build_mp4_transcode_command(
            input_path=input_path,
            output_path=output_path,
            source_audio_path=job.source_audio_path,
            clip_start=job.clip_start,
            clip_duration=job.clip_duration,
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        job.pid = proc.pid

        current_fps = 0.0
        current_speed = "1.0x"
        if proc.stdout:
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key == "fps":
                        try:
                            current_fps = float(val)
                        except ValueError:
                            pass
                    elif key == "speed":
                        current_speed = val
                    elif key == "out_time_us":
                        try:
                            out_us = int(val)
                            pct = min(0.99, max(0.0, out_us / target_duration_us))
                            job.progress = pct
                            if on_progress:
                                on_progress(pct, current_fps, current_speed)
                        except ValueError:
                            pass

        await proc.wait()
        job.pid = None
        if proc.returncode != 0:
            stderr = await proc.stderr.read() if proc.stderr else b""
            raise RuntimeError(f"MP4 transcode failed: {stderr.decode('utf-8', errors='replace')}")

    job.progress = 1.0
    return output_path
