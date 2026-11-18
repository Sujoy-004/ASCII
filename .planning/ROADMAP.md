# Roadmap: RGB ASCII & Retro FX Studio

## Overview

Transform the existing Python terminal video renderer into an end-to-end modern web studio and media transcoding service. The roadmap modernizes the existing Python core, establishes an interactive client-side WebGPU/WebGL2 studio designed via Stitch MCP (with an explicit user approval gate), builds a FastAPI backend for high-fidelity FFmpeg video and GIF exports, and deploys the entire three-tier architecture at $0/month using Git-driven configurations on Cloudflare Pages and Render.

## Phases

- [x] **Phase 1: Codebase Modernization & Core Engine Extraction** - Audit existing Python code, archive terminal runner, isolate core media algorithms, and ensure strict linting/typing. (completed 2026-11-17)
- [x] **Phase 2: Studio UI/UX Redesign & Client Shader Pipeline** - Prototype UI via Stitch MCP for explicit user approval, then build the React + WebGPU/WebGL2 interactive studio with media/webcam input and client-side exports. (completed 2026-11-18)
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
**Plans**: 3/3 plans complete (01-03 is UAT gap closure)

Plans:
**Wave 1**
- [x] 01-01-PLAN.md — Prune terminal-only modules, decouple playback loop into headless frame sink, and establish public engine facade in src/__init__.py.

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-02-PLAN.md — Prune terminal tests, update test doubles, and verify hermetic test pass, mypy typing, and ruff linting.

**Wave 3** *(gap closure — UAT Gap 1: real-TTY playback watchability)*
- [x] 01-03-PLAN.md — Restore watchable real-TTY playback: terminal-fit sizing via shutil.get_terminal_size plus isatty-guarded cursor-home animation in the dual-mode stdout sink; piped output stays byte-identical plain text.

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
**Plans**: 5 plans

Plans:
**Wave 1**
- [x] 02-01-PLAN.md — Prototype visual studio interface with Stitch MCP and secure explicit user design approval gate.

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-02-PLAN.md — Implement React 19 + TypeScript SPA studio shell with three-column docked layout, Viewport HUD, and blank-slate media/webcam ingestion.

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 02-03-PLAN.md — Build core Three.js WebGPU / TSL engine with WebGL2 fallback, dynamic monospace atlas, Rec. 601 ASCII node, and stage-gated pre-tone & CRT pipeline.

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 02-04-PLAN.md — Implement full 15 Grainrad primary retro shaders in TSL/WGSL and dynamic EffectInspector parameter panel.

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 02-05-PLAN.md — Implement client-side multi-format export suite (PNG, JPEG, SVG, TXT) and in-browser quick canvas recorder (WebM, animated GIF).

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
**Plans**: 4 plans

Plans:
**Wave 1**
- [ ] 03-01-PLAN.md — Build production FastAPI service core, single-job concurrency lock, Cloudflare ingress security, and SlowAPI rate limiting.

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 03-02-PLAN.md — Build low-memory FFmpeg video/GIF transcode engine, live progress telemetry parser, audio fallback seeking muxer, and storage janitor.

**Wave 3** *(blocked on Waves 1 & 2 completion)*
- [ ] 03-03-PLAN.md — Implement client-side Web Audio graph, DPI decoupling canvas lock, bounded chunk sequencer with backpressure, and retro terminal telemetry modal.

**Wave 4** *(blocked on Waves 1, 2 & 3 completion)*
- [ ] 03-04-PLAN.md — Configure Git-driven deployment via render.yaml and wrangler.toml, Neon SQL schema blueprint, and 512MB RAM / 0.1 vCPU benchmark suite.

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Codebase Modernization & Core Extraction | 3/3 | Complete    | 2026-11-17 |
| 2. Studio UI/UX Redesign & Client Shader Pipeline | 5/5 | Complete    | 2026-11-18 |
| 3. Backend API, High-Res Export & Deployment | 0/4 | Not started | - |

---
*Roadmap created: 2026-11-16*
*Last updated: 2026-11-16 after initialization*
