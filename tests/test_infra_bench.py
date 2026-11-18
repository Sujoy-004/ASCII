"""Unit and integration tests for Git-driven deployment blueprints and benchmark suite.

Validates render.yaml Render Blueprint, wrangler.toml Cloudflare Pages config,
SPA _redirects rule, Neon PostgreSQL database schema blueprint, and bench_export.py.
"""

from __future__ import annotations

from pathlib import Path
import shutil
from unittest.mock import MagicMock, patch
import yaml

import pytest

from bench_export import (
    BenchmarkResult,
    ProcessTreeMemorySampler,
    print_report,
    run_export_benchmark,
)


def test_render_blueprint_validity() -> None:
    """Verify render.yaml conforms to Render Blueprint specification for free-tier web service."""
    render_path = Path("render.yaml")
    assert render_path.exists(), "render.yaml must exist at repository root"

    with open(render_path, "r", encoding="utf-8") as f:
        blueprint = yaml.safe_load(f)

    assert "services" in blueprint, "render.yaml must define 'services'"
    services = blueprint["services"]
    assert len(services) >= 1, "render.yaml must have at least one service defined"

    web_svc = services[0]
    assert web_svc["type"] == "web"
    assert web_svc["name"] == "rgb-ascii-api"
    assert web_svc["runtime"] == "python"
    assert web_svc["plan"] == "free"
    assert web_svc["numInstances"] == 1
    assert web_svc["healthCheckPath"] == "/api/health"
    assert "--workers 1" in web_svc["startCommand"]
    assert "pip install -r requirements.txt" in web_svc["buildCommand"]

    # Verify environment variables
    env_keys = {item["key"]: item for item in web_svc.get("envVars", [])}
    assert "ENVIRONMENT" in env_keys
    assert env_keys["ENVIRONMENT"]["value"] == "production"
    assert "CORS_ORIGINS" in env_keys
    assert "TURNSTILE_SECRET_KEY" in env_keys
    assert env_keys["TURNSTILE_SECRET_KEY"].get("sync") is False
    assert "TURNSTILE_SITE_KEY" in env_keys
    assert env_keys["TURNSTILE_SITE_KEY"].get("sync") is False


def test_cloudflare_pages_configuration() -> None:
    """Verify wrangler.toml and web/public/_redirects for Cloudflare Pages edge deployment."""
    wrangler_path = Path("wrangler.toml")
    assert wrangler_path.exists(), "wrangler.toml must exist at repository root"
    content = wrangler_path.read_text(encoding="utf-8")
    assert 'name = "rgb-ascii"' in content
    assert 'pages_build_output_dir = "./web/dist"' in content

    redirects_path = Path("web/public/_redirects")
    assert redirects_path.exists(), "_redirects must exist in web/public/"
    redirects_text = redirects_path.read_text(encoding="utf-8").strip()
    assert redirects_text == "/*    /index.html   200", "SPA redirect rule must match Cloudflare Pages format"


def test_database_schema_ddl() -> None:
    """Verify docs/database-schema.sql contains valid PostgreSQL DDL with required tables and indexes."""
    schema_path = Path("docs/database-schema.sql")
    assert schema_path.exists(), "docs/database-schema.sql must exist"
    ddl = schema_path.read_text(encoding="utf-8")

    # Table definitions
    assert "CREATE TABLE IF NOT EXISTS users" in ddl
    assert "CREATE TABLE IF NOT EXISTS presets" in ddl
    assert "CREATE TABLE IF NOT EXISTS export_jobs" in ddl

    # Columns and constraints
    assert "user_id UUID NOT NULL REFERENCES users" in ddl
    assert "parameters JSONB NOT NULL" in ddl
    assert "is_public BOOLEAN NOT NULL DEFAULT FALSE" in ddl
    assert "format VARCHAR(10) NOT NULL" in ddl
    assert "peak_rss_mb NUMERIC(6, 2)" in ddl

    # Indexes
    assert "CREATE INDEX IF NOT EXISTS idx_presets_user_id ON presets (user_id);" in ddl
    assert "CREATE INDEX IF NOT EXISTS idx_presets_parameters_gin ON presets USING gin (parameters);" in ddl
    assert "CREATE INDEX IF NOT EXISTS idx_export_jobs_status ON export_jobs (status);" in ddl
    assert "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);" in ddl


def test_process_tree_memory_sampler() -> None:
    """Verify ProcessTreeMemorySampler correctly samples current and child process RSS."""
    sampler = ProcessTreeMemorySampler(interval_sec=0.010)
    current_rss = sampler.current_rss_bytes()
    assert current_rss > 0, "Current RSS should be greater than zero bytes"

    sampler.start()
    # Allocate small buffer to verify memory delta tracking
    buf = bytearray(5 * 1024 * 1024)
    assert len(buf) == 5 * 1024 * 1024
    peak = sampler.stop()
    assert peak >= current_rss, "Peak RSS must be at least initial RSS"


def test_process_tree_memory_sampler_child_aggregation() -> None:
    """Verify sampler aggregates recursive children memory info."""
    sampler = ProcessTreeMemorySampler(interval_sec=0.010)

    # Mock child process with 50 MB RSS
    mock_child = MagicMock()
    mock_child.memory_info.return_value.rss = 50 * 1024 * 1024

    with patch.object(sampler._parent, "children", return_value=[mock_child]):
        total = sampler.current_rss_bytes()
        parent_rss = sampler._parent.memory_info().rss
        assert total == parent_rss + (50 * 1024 * 1024)


def test_benchmark_result_evaluation_and_report(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify BenchmarkResult thresholds and formatted report output."""
    res_pass = BenchmarkResult(
        duration_sec=30.0,
        elapsed_sec=12.5,
        peak_rss_mb=135.0,
        format="mp4",
        passed=True,
        details="All constraints satisfied",
    )
    print_report(res_pass)
    captured = capsys.readouterr()
    assert "[PASS] CONSTRAINTS SATISFIED" in captured.out
    assert "135.00 MB" in captured.out

    res_fail = BenchmarkResult(
        duration_sec=30.0,
        elapsed_sec=85.0,
        peak_rss_mb=275.0,
        format="mp4",
        passed=False,
        details="Threshold breached",
    )
    print_report(res_fail)
    captured_fail = capsys.readouterr()
    assert "[FAIL] CONSTRAINTS BREACHED" in captured_fail.out


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg executable not found on system PATH")
@pytest.mark.asyncio
async def test_run_export_benchmark_quick() -> None:
    """Run an actual quick benchmark execution (3-second synthetic clip) and verify metrics."""
    result = run_export_benchmark(
        duration_sec=3.0,
        fps=24,
        format="mp4",
        threshold_rss_mb=250.0,
        threshold_time_sec=25.0,
    )
    assert result.passed is True
    assert result.peak_rss_mb < 250.0
    assert result.elapsed_sec < 25.0
