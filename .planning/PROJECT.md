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

### Active

- [ ] **Codebase Modernization**: Audit `src/`, strip dead/terminal-bound code, optimize core math routines, and ensure 100% clean typing (`mypy`) and linting (`ruff`).
- [ ] **FastAPI Backend Transition**: Repurpose core media algorithms into a clean, modern FastAPI service with endpoints for media upload, frame processing, and FFmpeg video transcoding.
- [ ] **Client-Side FX Pipeline**: WebGPU / Canvas shaders delivering real-time interactive previews of ASCII art, dithering, halftone, matrix rain, VHS/scanlines, noise, and color adjustments inspired by Grainrad.
- [ ] **Multi-Format Input**: Support drag-and-drop file ingestion (PNG, JPG, WebP, GIF, MP4, WebM) and live browser webcam feed.
- [ ] **Comprehensive Export System**: Instant client-side export (PNG, JPEG, SVG, Text/ASCII `.txt`, HTML) plus backend export for rendered MP4 video and animated GIF.
- [ ] **Stitch MCP UI/UX Redesign**: Modern, polished studio interface designed iteratively using Stitch MCP, with full user review before code implementation.
- [ ] **Git-Driven $0/Month Infrastructure**: Production configuration via `render.yaml` (Render Web Service for FastAPI) and `wrangler.toml` (Cloudflare Pages for frontend SPA).
- [ ] **Neon PostgreSQL Scaffolding**: Schema and connection scaffolding for future preset/project persistence, keeping v1 completely operational as a stateless zero-cost tool.

### Out of Scope

- Terminal interactive playback engine — Pivoting entirely to Web platform; terminal-only components (`src/terminal.py`) archived.
- Proprietary Grainrad source code or branding duplication — Clean-room functional reproduction of retro shader and export features.
- Mandatory user auth or paid cloud databases for v1 — Stateless utility first to eliminate cost and setup barriers.
- Dedicated cloud GPU instances — Real-time processing runs on client hardware (WebGPU/Canvas), exports run on free CPU compute.

## Context

- The existing repository is a robust, hermetically tested (~387 tests) Python 3.10+ command-line video player with proven FFmpeg integration, luminance mapping, and color quantization.
- Grainrad (`grainrad.com`) demonstrates strong demand for accessible, browser-native retro graphics generators with rich parametric controls and diverse export formats.
- Cloudflare Pages provides unlimited free static hosting and edge speed; Render provides a free tier for Python web services (FastAPI + FFmpeg); Neon provides free serverless PostgreSQL.

## Constraints

- **Budget**: $0/month strict target across all cloud services (Cloudflare Pages free tier, Render free tier web service, Neon free tier).
- **Tech Stack (Frontend)**: Modern SPA (Vite / React / TypeScript / Tailwind CSS / WebGPU / Canvas) deployed to Cloudflare Pages.
- **Tech Stack (Backend)**: Python 3.10+ with FastAPI, Uvicorn, and FFmpeg deployed to Render via `render.yaml`.
- **UI Approval Gate**: All Stitch MCP visual designs must be reviewed and explicitly approved by the user before frontend code implementation begins.
- **Hermetic Testing**: Comprehensive unit and integration test coverage maintained throughout modernization and expansion.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid Client FX + Backend Export | Client-side shaders provide 60fps interactive parameter adjustments; backend provides heavy FFmpeg video rendering | — Pending |
| Pivot Entirely to Web Application | Maximizes user accessibility and aligns with modern creative workflow; terminal player archived | — Pending |
| Stateless v1 Utility Mode | Eliminates authentication hurdles and database runtime costs, achieving instant $0/month deployment | — Pending |
| Git-Driven Deployment (`render.yaml` & `wrangler.toml`) | Infrastructure-as-code enables reproducible single-push deployments to Cloudflare and Render | — Pending |

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
*Last updated: 2026-11-16 after initialization*
