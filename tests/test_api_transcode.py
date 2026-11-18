"""Hermetic tests for low-memory FFmpeg transcoding and ephemeral storage janitor."""

from __future__ import annotations

import json
import os
import time
from unittest.mock import MagicMock, patch
import pytest

from src.api.jobs import ExportJob, ExportJobManager
from src.api.janitor import ExportJanitor
from src.api.transcode import (
    build_gif_transcode_commands,
    build_mp4_transcode_command,
    mux_fallback_audio,
    parse_progress_line,
    validate_assembled_media,
)


@pytest.fixture(autouse=True)
def clean_manager_and_janitor():
    """Reset ExportJobManager before each test."""
    manager = ExportJobManager.get_instance()
    manager.reset()
    yield
    manager.reset()


def test_build_mp4_transcode_command():
    """build_mp4_transcode_command enforces -threads 1, ultrafast preset, and libx264 per D-01 and D-07."""
    cmd = build_mp4_transcode_command(
        input_path="/tmp/test/input.webm",
        output_path="/tmp/test/output.mp4",
    )
    cmd_str = " ".join(cmd)
    assert "-threads 1" in cmd_str
    assert "-preset ultrafast" in cmd_str
    assert "-c:v libx264" in cmd_str
    assert "-crf 23" in cmd_str
    assert "-pix_fmt yuv420p" in cmd_str
    assert "-movflags +faststart" in cmd_str
    assert "-c:a aac" in cmd_str
    assert "-progress pipe:1" in cmd_str
    assert cmd[-1] == "/tmp/test/output.mp4"


def test_build_mp4_transcode_with_fallback_audio(tmp_path):
    """build_mp4_transcode_command incorporates pre-input seeking and audio muxing per D-05."""
    dummy_audio = tmp_path / "audio.mp4"
    dummy_audio.write_bytes(b"mockaudio")

    cmd = build_mp4_transcode_command(
        input_path="/tmp/test/input.webm",
        output_path="/tmp/test/output.mp4",
        source_audio_path=str(dummy_audio),
        clip_start=5.25,
        clip_duration=12.5,
    )
    cmd_str = " ".join(cmd)
    assert "-ss 5.250" in cmd_str
    assert "-t 12.500" in cmd_str
    assert "-map 1:v:0 -map 0:a:0?" in cmd_str
    assert "aresample=async=1:first_pts=0" in cmd_str
    assert "-shortest" in cmd_str
    assert "-threads 1" in cmd_str


def test_build_gif_transcode_commands():
    """build_gif_transcode_commands generates memory-efficient two-pass palettegen commands per D-07."""
    pass1, pass2 = build_gif_transcode_commands(
        input_path="/tmp/test/input.webm",
        output_path="/tmp/test/output.gif",
        palette_path="/tmp/test/palette.png",
        fps=12,
    )
    p1_str = " ".join(pass1)
    p2_str = " ".join(pass2)

    # Pass 1 verifies 128 colors and -an
    assert "palettegen=max_colors=128" in p1_str
    assert "-threads 1" in p1_str
    assert "-an" in p1_str
    assert pass1[-1] == "/tmp/test/palette.png"

    # Pass 2 verifies Bayer ordered dithering scale 3
    assert "paletteuse=dither=bayer:bayer_scale=3" in p2_str
    assert "-threads 1" in p2_str
    assert "-an" in p2_str
    assert "-progress pipe:1" in p2_str
    assert pass2[-1] == "/tmp/test/output.gif"


def test_mux_fallback_audio_flags():
    """mux_fallback_audio builds correct pre-input seeking command."""
    cmd = mux_fallback_audio(
        source_path="/tmp/source.mp4",
        canvas_video_path="/tmp/canvas.webm",
        output_path="/tmp/out.mp4",
        start_sec=2.0,
        duration_sec=8.0,
    )
    cmd_str = " ".join(cmd)
    assert "-ss 2.000" in cmd_str
    assert "-t 8.000" in cmd_str
    assert "-c:v copy" in cmd_str
    assert "-c:a aac" in cmd_str
    assert "-shortest" in cmd_str


def test_parse_progress_line():
    """parse_progress_line parses key=value format from FFmpeg -progress pipe:1."""
    assert parse_progress_line("out_time_us=5000000") == {"out_time_us": "5000000"}
    assert parse_progress_line("fps=29.97") == {"fps": "29.97"}
    assert parse_progress_line("speed=1.52x") == {"speed": "1.52x"}
    assert parse_progress_line("progress=continue") == {"progress": "continue"}
    assert parse_progress_line("invalid_line_without_equal") == {}


def test_validate_assembled_media(tmp_path):
    """validate_assembled_media inspects media dimensions and duration, rejecting invalid inputs per D-07."""
    empty_file = tmp_path / "empty.webm"
    empty_file.write_bytes(b"")

    with pytest.raises(ValueError, match="is empty or does not exist"):
        validate_assembled_media(str(empty_file), "mp4")

    # Mock ffprobe returning valid 1080p 10s video
    valid_file = tmp_path / "valid.webm"
    valid_file.write_bytes(b"WEBM_VALID_HEADER")

    mock_probe_output = json.dumps({
        "streams": [{"width": 1920, "height": 1080, "duration": "10.0"}],
        "format": {"duration": "10.0"},
    })

    with patch("shutil.which", return_value="/usr/bin/ffprobe"), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_probe_output, stderr="", returncode=0)
        res = validate_assembled_media(str(valid_file), "mp4", max_duration=60.0)
        assert res["width"] == 1920
        assert res["height"] == 1080
        assert res["duration"] == 10.0

    # Duration exceeded -> ValueError
    mock_long_probe = json.dumps({
        "streams": [{"width": 1920, "height": 1080, "duration": "95.0"}],
        "format": {"duration": "95.0"},
    })
    with patch("shutil.which", return_value="/usr/bin/ffprobe"), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_long_probe, stderr="", returncode=0)
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            validate_assembled_media(str(valid_file), "mp4", max_duration=60.0)

    # GIF resolution exceeding 720p -> ValueError
    mock_hi_res_gif = json.dumps({
        "streams": [{"width": 1920, "height": 1080, "duration": "5.0"}],
        "format": {"duration": "5.0"},
    })
    with patch("shutil.which", return_value="/usr/bin/ffprobe"), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_hi_res_gif, stderr="", returncode=0)
        with pytest.raises(ValueError, match="exceeds 720p limit"):
            validate_assembled_media(str(valid_file), "gif", max_duration=15.0)


@pytest.mark.asyncio
async def test_janitor_active_protection_and_sweeping(tmp_path):
    """ExportJanitor protects active jobs and PIDs, and purges expired artifacts per D-08."""
    storage_dir = tmp_path / "exports"
    storage_dir.mkdir()
    janitor = ExportJanitor(storage_dir=storage_dir, sweep_interval=1)
    manager = ExportJobManager(base_storage_dir=storage_dir)

    # 1. Active job in 'capturing' state with active PID (current process PID)
    job1_dir = storage_dir / "job_active_1"
    job1_dir.mkdir()
    (job1_dir / "input.webm").write_bytes(b"active_data")
    job1 = ExportJob(
        id="job_active_1",
        token_hash="hash1",
        format="mp4",
        duration=10.0,
        fps=30,
        state="capturing",
        created_at=time.time(),
        updated_at=time.time(),
        pid=os.getpid(),
    )
    manager._jobs["job_active_1"] = job1

    # 2. Expired completed job older than 600s
    job2_dir = storage_dir / "job_expired_2"
    job2_dir.mkdir()
    (job2_dir / "output.mp4").write_bytes(b"old_data")
    # Backdate mtime by 700s
    old_time = time.time() - 700
    os.utime(job2_dir, (old_time, old_time))
    job2 = ExportJob(
        id="job_expired_2",
        token_hash="hash2",
        format="mp4",
        duration=10.0,
        fps=30,
        state="completed",
        created_at=old_time,
        updated_at=old_time,
    )
    manager._jobs["job_expired_2"] = job2

    # Patch ExportJobManager.get_instance to return test manager
    with patch("src.api.janitor.ExportJobManager.get_instance", return_value=manager):
        sweep_result = await janitor.run_sweep()

    # Active job MUST still exist
    assert job1_dir.exists()
    assert (job1_dir / "input.webm").exists()

    # Expired job MUST be purged
    assert not job2_dir.exists()
    assert sweep_result["purged_jobs"] == 1


@pytest.mark.asyncio
async def test_janitor_inactivity_timeout_for_stalled_upload(tmp_path):
    """ExportJanitor fails stalled upload jobs that exceed 60s inactivity per D-08."""
    storage_dir = tmp_path / "exports"
    storage_dir.mkdir()
    janitor = ExportJanitor(storage_dir=storage_dir)
    manager = ExportJobManager(base_storage_dir=storage_dir)

    # Stalled job updated 75 seconds ago
    stalled_time = time.time() - 75
    job = ExportJob(
        id="job_stalled",
        token_hash="hash_s",
        format="mp4",
        duration=10.0,
        fps=30,
        state="uploading",
        created_at=stalled_time,
        updated_at=stalled_time,
    )
    manager._jobs["job_stalled"] = job
    manager._active_job_id = "job_stalled"

    with patch("src.api.janitor.ExportJobManager.get_instance", return_value=manager):
        await janitor.run_sweep()

    # Stalled job must have transitioned to failed
    assert job.state == "failed"
    assert "inactivity timeout" in (job.error or "").lower()
    # Concurrency lock must be released
    assert manager._active_job_id is None
