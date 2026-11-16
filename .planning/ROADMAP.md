# Roadmap: RGB ASCII & Retro FX Studio

## Overview

Transform the existing Python terminal video renderer into an end-to-end modern web studio and media transcoding service. The roadmap modernizes the existing Python core, establishes an interactive client-side WebGPU/WebGL2 studio designed via Stitch MCP (with an explicit user approval gate), builds a FastAPI backend for high-fidelity FFmpeg video and GIF exports, and deploys the entire three-tier architecture at $0/month using Git-driven configurations on Cloudflare Pages and Render.

## Phases

- [ ] **Phase 1: Codebase Modernization & Core Engine Extraction** - Audit existing Python code, archive terminal runner, isolate core media algorithms, and ensure strict linting/typing.
- [ ] **Phase 2: Studio UI/UX Redesign & Client Shader Pipeline** - Prototype UI via Stitch MCP for explicit user approval, then build the React + WebGPU/WebGL2 interactive studio with media/webcam input and client-side exports.
- [ ] **Phase 3: Backend API, High-Res Export & Git-Driven Deployment** - FastAPI service, FFmpeg video/GIF transcoding with audio sync, Neon PostgreSQL scaffolding, and zero-cost cloud deployment via `render.yaml` and `wrangler.toml`.

## Phase Details

### Phase 1: Codebase Modernization & Core Engine Extraction
**Goal**: Audit, clean, and decouple the existing Python codebase, archiving terminal-only dependencies and exposing a clean, robust media transformation core with 100% test, lint, and type health.
**Depends on**: Nothing (first phase)
**Requirements**: MODERN-01, MODERN-02, MODERN-03
**Success Criteria** (what must be TRUE):
  1. Terminal-specific modules (`src/terminal.py`) and playback loops are archived or decoupled without broken imports or orphaned code.
  2. Core media modules (`renderer.py`, `video.py`, `audio.py`, `config.py`) import cleanly and expose clear interfaces for video decoding, luminance mapping, and box-averaging.
  3. Static type checking (`python -m mypy`) and linting (`python -m ruff check .`) pass with zero errors across all Python sources.
  4. Hermetic test suite (`pytest`) runs cleanly with 100% passing tests on modernized core components.
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md — Prune terminal-only modules, decouple playback loop into headless frame sink, and establish public engine facade in src/__init__.py.
- [ ] 01-02-PLAN.md — Prune terminal tests, update test doubles, and verify hermetic test pass, mypy typing, and ruff linting.

---

### Phase 2: Studio UI/UX Redesign & Client Shader Pipeline
**Goal**: Prototype studio interface via Stitch MCP, obtain explicit user approval on visual designs, and build the React + TypeScript SPA with a 60 FPS WebGPU/WebGL2 retro shader engine, drag-and-drop/webcam media input, and instant client-side exports.
**Depends on**: Phase 1
**Requirements**: STUDIO-01, STUDIO-02, STUDIO-03, SHADER-01, SHADER-02, SHADER-03, SHADER-04, MEDIA-01, MEDIA-02, MEDIA-03
**Success Criteria** (what must be TRUE):
  1. Stitch MCP UI/UX design is presented for user review and explicitly approved by the user before visual frontend code implementation begins.
  2. User can drag and drop images (PNG, JPG, WebP, GIF) or video (MP4, WebM) and see immediate real-time retro shader transformations in the canvas viewport.
  3. User can activate live webcam feed via `getUserMedia` and adjust ASCII character sets (Standard, Dense, Simple, Blocks), cell scaling, dithering, halftone, and tone controls in real time.
  4. Client-side export downloads instant high-resolution PNG, JPEG, SVG, or plain ASCII text (`.txt`) files without server dependency.
  5. Automatic fallback to WebGL2 activates seamlessly on browsers or devices without WebGPU support.
**Plans**: 3 plans

Plans:
- [ ] 02-01: Generate Stitch MCP design prototypes, conduct user design review, and secure explicit approval.
- [ ] 02-02: Implement SPA studio shell with React, Vite, Tailwind CSS, Zustand store, and interactive canvas viewport.
- [ ] 02-03: Implement WebGPU/WebGL2 shader pipeline (ASCII, Dither, Halftone, VHS, Adjustments), media/webcam loaders, and client export.

---

### Phase 3: Backend API, High-Res Export & Git-Driven Deployment
**Goal**: Build FastAPI backend service around the modernized core, connect heavy FFmpeg video and animated GIF export with audio synchronization, scaffold Neon PostgreSQL, and configure automated Git-driven deployments on Cloudflare and Render at $0/month.
**Depends on**: Phase 2
**Requirements**: EXPORT-01, EXPORT-02, EXPORT-03, EXPORT-04, INFRA-01, INFRA-02, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. User can request high-resolution MP4 video or animated GIF export, and FastAPI/FFmpeg delivers rendered video with preserved audio sync.
  2. Backend processes video transcoding in streaming chunks via temporary files, operating strictly within Render's 512MB RAM ceiling.
  3. Background pre-warming (`GET /api/health`) wakes up hibernating Render free instances, accompanied by transparent client-side progress indicators.
  4. `wrangler.toml` and `render.yaml` provide complete Git-driven deployment to Cloudflare Pages and Render on push to `main`.
  5. Neon Serverless PostgreSQL connection and schema scaffolding is configured and documented for future user/preset persistence.
  6. Complete production deployment runs verified at $0/month with zero ongoing infrastructure charges.
**Plans**: 2 plans

Plans:
- [ ] 03-01: Build FastAPI service with `/api/export/video` and `/api/health`, chunked FFmpeg transcoding, and Neon DB scaffolding.
- [ ] 03-02: Configure `render.yaml` and `wrangler.toml`, verify free-tier resource limits, connect client export dialog, and validate end-to-end production deployment.

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Codebase Modernization & Core Extraction | 0/2 | Not started | - |
| 2. Studio UI/UX Redesign & Client Shader Pipeline | 0/3 | Not started | - |
| 3. Backend API, High-Res Export & Deployment | 0/2 | Not started | - |

---
*Roadmap created: 2026-11-16*
*Last updated: 2026-11-16 after initialization*
