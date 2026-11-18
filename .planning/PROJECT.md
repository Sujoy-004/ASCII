# RGB ASCII & Retro FX Studio

## What This Is

A modern, high-performance browser-based retro visual effects and ASCII studio for images, videos, and live webcam streams. It delivers instant, GPU-accelerated client-side previews (ASCII, dithering, halftone, CRT/VHS, matrix rain, and color grading) alongside a Python FastAPI backend for high-fidelity FFmpeg-driven exports and processing. Built for digital artists, designers, and terminal enthusiasts seeking versatile retro graphics in a responsive studio interface.

## Core Value

Instant, real-time retro visual transformations and high-fidelity media export across web and video formats, operating reliably at $0/month on free-tier cloud infrastructure.

## Requirements

### Validated

- ✓ RGB24 pixel to Rec. 601 perceived luminance mapping — existing (`src/renderer.py`)
- ✓ 24-bit True Color ANSI escape generation and half-block (`\u2580`) color packing — existing (`src/renderer.py`)
- ✓ Area-averaging (`resize_rgb24_area`) and nearest-neighbor resampling — existing (`src/renderer.py`)
- ✓ Subprocess FFmpeg video decoding with stream error and container diagnostics — existing (`src/video.py`)
- ✓ Temporal smoothing (`TemporalSmoother`) exponential RGB24 blending — existing (`src/smoothing.py`)
- ✓ Frame pacing and deadline scheduling models (`FrameClock`, `PlaybackTimeline`) — existing (`src/timing.py`, `src/sync.py`)
- ✓ Codebase Modernization: headless frame sink protocol, 36-symbol public facade, 100% type/lint health — v1.0 (`src/__init__.py`)
- ✓ Stitch MCP UI/UX Redesign: monochrome Grainrad-inspired theme tokens, three-column docked studio layout, responsive Viewport HUD — v1.0 (`web/src/`)
- ✓ Client-Side FX Pipeline: 60 FPS Three.js WebGPU / TSL engine with automatic WebGL2 fallback, dynamic monospace atlas, and 16 retro shaders — v1.0 (`web/src/engine/`)
- ✓ Multi-Format Media Ingestion: Drag-and-drop local image/video files at native aspect ratios, plus live browser webcam stream via `getUserMedia` — v1.0 (`web/src/components/`)
- ✓ Client-Side Multi-Format Export: Instant raster PNG/JPEG, monochrome/TrueColor vector SVG, Rec. 601 plain text (`.txt`), and quick WebM/GIF clips — v1.0 (`web/src/export/`)
- ✓ Production FastAPI Microservice: Turnstile bot protection, Cloudflare CIDR validation, constant-time `X-Job-Token` checks, single-use download tokens, and SlowAPI rate limiting — v1.0 (`src/api/`)
- ✓ Low-Memory Server Transcoding: Bounded chunk sequencer, Web Audio graph persistence, DPI decoupling (1080p/720p), and low-memory FFmpeg video/GIF transcode (<137MB RSS) — v1.0 (`src/api/transcode.py`)
- ✓ Git-Driven $0/Month Infrastructure: Cloudflare Pages edge hosting (`wrangler.toml`), Render Python Web Service (`render.yaml`), and Neon PostgreSQL schema scaffolding (`docs/database-schema.sql`) — v1.0

### Active (Next Milestone Candidates)

- [ ] **PERSIST-01**: User accounts and project workspace persistence via Neon Serverless PostgreSQL.
- [ ] **PERSIST-02**: Community preset sharing gallery allowing artists to publish and clone effect recipes.
- [ ] **PERSIST-03**: Standalone Three.js 3D embeddable HTML export package.
- [ ] **PERSIST-04**: Extended retro shader packs (Voronoi crystallization, Audio-reactive scanlines, Pixel sorting enhancements).

### Out of Scope

- Terminal interactive playback engine — Pivoted entirely to Web platform; terminal-only components (`src/terminal.py`) archived.
- Proprietary Grainrad source code or branding duplication — Clean-room functional reproduction of retro shader and export features.
- Mandatory user auth or paid cloud databases for v1 — Stateless utility first to eliminate cost and setup barriers.
- Dedicated cloud GPU instances — Real-time processing runs on client hardware (WebGPU/Canvas), exports run on free CPU compute.
- Unbounded video file uploads — Enforced 60-second video length limit on video exports to guarantee stability within 512MB RAM.

## Context

- Shipped Milestone v1.0 with 18,162 lines of code across Python (12,780 LOC) and TypeScript (5,382 LOC).
- Frontend: React 19, Vite 8, Tailwind CSS v4, Three.js WebGPU / TSL, deployed on Cloudflare Pages (`https://rgb-ascii.pages.dev`).
- Backend: Python 3.10+, FastAPI, Uvicorn, FFmpeg, deployed on Render Free Web Service (`render.yaml`).
- Database Scaffolding: Neon Serverless PostgreSQL schema (`docs/database-schema.sql`) prepared for v2 user and preset persistence.
- Complete suite of 435 automated tests passing with zero regressions, strict type safety (`mypy`), and fast linting (`ruff`).

## Constraints

- **Budget**: $0/month strict target across all cloud services (Cloudflare Pages free tier, Render free tier web service, Neon free tier).
- **Tech Stack (Frontend)**: Modern SPA (Vite / React / TypeScript / Tailwind CSS / WebGPU / Canvas) deployed to Cloudflare Pages.
- **Tech Stack (Backend)**: Python 3.10+ with FastAPI, Uvicorn, and FFmpeg deployed to Render via `render.yaml`.
- **UI Approval Gate**: All Stitch MCP visual designs must be reviewed and explicitly approved by the user before frontend code implementation begins.
- **Hermetic Testing**: Comprehensive unit and integration test coverage maintained throughout modernization and expansion.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid Client FX + Backend Export | Client-side shaders provide 60fps interactive parameter adjustments; backend provides heavy FFmpeg video rendering | ✓ Good (60fps preview with 0 server CPU; transcode peak RSS 136.29 MB < 512 MB ceiling) |
| Pivot Entirely to Web Application | Maximizes user accessibility and aligns with modern creative workflow; terminal player archived | ✓ Good (Web studio deployed to Cloudflare Pages; live at rgb-ascii.pages.dev) |
| Stateless v1 Utility Mode | Eliminates authentication hurdles and database runtime costs, achieving instant $0/month deployment | ✓ Good (Zero cloud bills, instant friction-free access) |
| Git-Driven Deployment (`render.yaml` & `wrangler.toml`) | Infrastructure-as-code enables reproducible single-push deployments to Cloudflare and Render | ✓ Good (Automated deployment directly from main branch) |
| Client-Side WebGPU Shaders with TSL | Next-generation WebGPU performance with clean WebGL2 fallback via Three.js node system | ✓ Good (60 FPS rendering across WebGPU and WebGL2 hardware) |
| DPI Decoupling & Bounded Backpressure | Protects export render quality from viewport zoom and client memory bloat | ✓ Good (Predictable 1080p/720p output with max 5 chunks in flight) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-18 after v1.0 milestone*
