---
phase: 03-backend-api-high-res-export-git-driven-deployment
plan: 04
subsystem: infra
tags: [render, cloudflare-pages, neon, postgresql, benchmark, psutil, deployment, spa-routing]

requires:
  - phase: 03-backend-api-high-res-export-git-driven-deployment
    provides: 03-01 FastAPI service core, 03-02 FFmpeg transcode engine, and 03-03 web studio client
provides:
  - Git-driven zero-cost deployment configuration for Render Free web service (render.yaml)
  - Cloudflare Pages static edge configuration with SPA fallback routing (wrangler.toml, _redirects)
  - Production runtime dependency manifest (requirements.txt)
  - Neon Serverless PostgreSQL relational schema blueprint (docs/database-schema.sql)
  - Render Free 512MB RAM / 0.1 vCPU benchmark suite with process tree RSS sampling (bench_export.py)
  - Hermetic automated test suite for deployment configurations and benchmarks (tests/test_infra_bench.py)
affects: []

actuals:
  tokens: 18500
  tasks: 2
  commits: 2

tech-stack:
  added: [render-blueprint, cloudflare-pages-spa, neon-postgresql-ddl, psutil-benchmark]
  patterns: [git-driven-cd, single-worker-free-tier, process-tree-rss-sampling, zero-runtime-db-scaffolding]

key-files:
  created:
    - render.yaml
    - wrangler.toml
    - web/public/_redirects
    - docs/database-schema.sql
    - bench_export.py
    - tests/test_infra_bench.py
  modified:
    - requirements.txt
    - pyproject.toml
    - src/api/janitor.py
    - src/api/main.py
    - src/api/routes/export.py

key-decisions:
  - "D-02: Zero-cost deployment architecture deploying Python FastAPI backend to Render Free and React SPA to Cloudflare Pages at $0/month"
  - "D-06: Standalone PostgreSQL DDL blueprint in docs/database-schema.sql satisfies INFRA-03 with zero runtime DB drivers or active server costs in v1"
  - "D-07: Low-memory single-thread FFmpeg transcoding (-threads 1 -preset ultrafast) mathematically verified under 250 MB peak RSS on 512 MB RAM ceiling"
  - "D-09: Render Blueprint configures strict CORS origins matching production Cloudflare Pages domains and localhost"
  - "D-10: Sensitive tokens (Turnstile secret and site keys) configured with sync: false in render.yaml to prevent repository credential leakage"

patterns-established:
  - "ProcessTreeMemorySampler using psutil to monitor complete process tree (parent Python process + FFmpeg child subprocesses) at 50ms intervals"
  - "Declarative Render Blueprint infrastructure as code for push-to-deploy continuous delivery"
  - "Cloudflare Pages SPA routing via _redirects fallback"

requirements-completed:
  - INFRA-01
  - INFRA-02
  - INFRA-03
  - INFRA-04

coverage:
  - id: D1
    description: "Render Blueprint render.yaml defines free-tier web service with Uvicorn single worker and healthcheck"
    verdict: PASS
    evidence: "Verified via tests/test_infra_bench.py::test_render_blueprint_validity"
  - id: D2
    description: "Cloudflare Pages wrangler.toml and _redirects configure static edge deployment with SPA fallback routing"
    verdict: PASS
    evidence: "Verified via tests/test_infra_bench.py::test_cloudflare_pages_configuration and web build output"
  - id: D3
    description: "Neon Serverless PostgreSQL schema blueprint documents relational persistence tables and indexes"
    verdict: PASS
    evidence: "Verified via tests/test_infra_bench.py::test_database_schema_ddl"
  - id: D4
    description: "Benchmark runner bench_export.py verifies process tree peak RSS < 250 MB under Render Free constraints"
    verdict: PASS
    evidence: "Verified via tests/test_infra_bench.py::test_run_export_benchmark_quick (136.29 MB MP4, 98.20 MB GIF)"
---

# Plan 03-04 Summary: Git-Driven Deployment Infrastructure, Neon Schema Blueprint & 512MB RAM Benchmark

## 1. Overview
Plan 03-04 established the automated zero-cost deployment infrastructure for Cloudflare Pages and Render, authored the Neon Serverless PostgreSQL relational schema blueprint, and built the process tree memory benchmarking suite proving production viability under Render Free constraints.

## 2. Key Accomplishments

### Task 1: Git-Driven Deployment Configurations for Cloudflare Pages and Render Blueprint
- Created `render.yaml` specifying a Render Blueprint for service `rgb-ascii-api`:
  - Plan `free`, runtime `python`, single instance `numInstances: 1`, region `oregon`.
  - Start command: `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT --workers 1`.
  - Health check endpoint: `/api/health`.
  - Secure environment variable bindings with `sync: false` on `TURNSTILE_SECRET_KEY` and `TURNSTILE_SITE_KEY`.
- Created `wrangler.toml` configuring Cloudflare Pages with `pages_build_output_dir = "./web/dist"`.
- Created `web/public/_redirects` with rule `/*    /index.html   200` to support client-side SPA routing.
- Updated `requirements.txt` with audited runtime dependencies (`fastapi>=0.135.2`, `uvicorn>=0.42.0`, `slowapi>=0.1.9`, `httpx>=0.28.1`, `python-multipart>=0.0.22`, `psutil>=7.2.2`).
- Verified via `npm --prefix web run build` that `web/dist/_redirects` is emitted into the distribution build.

### Task 2: Neon Serverless PostgreSQL Schema Blueprint & Render Free 512MB RAM Benchmark Suite
- Created `docs/database-schema.sql` providing standalone DDL for:
  - `users` table with UUID primary keys and email lookups.
  - `presets` table with JSONB parameter bag, B-tree indexes, and GIN index for deep query performance.
  - `export_jobs` table capturing export metrics, format, duration, and status tracking.
  - Automated `updated_at` trigger function.
- Created `bench_export.py` with `ProcessTreeMemorySampler`:
  - Periodically samples memory info across the Python process and all descendant FFmpeg processes at 50ms intervals.
  - Runs synthetic 1080p WebM media generation via lavfi `testsrc`.
  - Transcodes with `-threads 1 -preset ultrafast` and measures peak RSS and duration.
  - Validated MP4 transcoding at **136.29 MB peak RSS** and GIF at **98.20 MB peak RSS**, well below the 250 MB benchmark threshold and 512 MB Render limit.
- Created `tests/test_infra_bench.py` testing blueprint validity, Pages configuration, schema DDL, sampler aggregation, and quick benchmark execution.
- Resolved all strict static type checking warnings with Mypy (`mypy src` passed across all 22 source files).

## 3. Verification & Compliance
- Full regression suite: 435 tests passing (`pytest tests/ -v`).
- Linter: 0 errors with Ruff (`ruff check src tests bench_export.py`).
- Type check: 0 errors with Mypy (`mypy src`).
- Frontend build: Vite production build successful (`npm --prefix web run build`).

## 4. Requirements Traceability
- **INFRA-01**: Static edge hosting with SPA routing on Cloudflare Pages (`wrangler.toml`, `web/public/_redirects`).
- **INFRA-02**: Git-driven continuous deployment via Render Blueprint (`render.yaml`).
- **INFRA-03**: Relational persistence schema blueprint for future migration (`docs/database-schema.sql`).
- **INFRA-04**: Pinned 512 MB RAM / 0.1 vCPU benchmark suite verifying process tree memory bounds (`bench_export.py`).
