# Project Research Summary

**Project:** RGB ASCII & Retro FX Studio
**Domain:** Browser-Based GPU Visual Effects & Edge/Cloud Media Service
**Researched:** 2026-11-16
**Confidence:** HIGH

## Executive Summary

The project transforms an existing Python terminal RGB ASCII video player into a modern, browser-based visual effects studio and export workstation. Inspired by the functional architecture of Grainrad (`grainrad.com`), the application provides instantaneous, real-time retro visual transformations (ASCII art, dithering, halftone patterns, VHS scanlines, matrix rain, and tone grading) on images, videos, and live webcam feeds.

The system adopts a hybrid client-edge / server-export architecture optimized for zero cloud operational costs ($0/month):
1. **Frontend:** A responsive single-page studio application deployed to Cloudflare Pages (`wrangler.toml`), leveraging WebGPU/Canvas shaders for zero-latency 60 FPS previews and client-side exports (PNG, JPEG, SVG, Text).
2. **Backend:** A modernized FastAPI Python service deployed as a free-tier web service on Render (`render.yaml`), utilizing our existing FFmpeg decoding and transcoding integration to handle heavy video export tasks (MP4, animated GIF).
3. **Database:** Neon Serverless PostgreSQL is pre-configured and scaffolded for future project and preset sharing, while remaining inactive in v1 to preserve the $0/month budget.

Key risks include Render free-tier cold-start latency, memory constraints on 512MB RAM containers, and browser WebGPU compatibility. These are proactively mitigated through client-side autonomy, fallback WebGL2 shaders, bounded streaming video chunking, and pre-warming background pings.

## Key Findings

### Recommended Stack

The optimal modern stack combines web edge hosting with high-performance client rendering and a lean Python transcoding backend:

- **Client Framework:** React 18+ with TypeScript, Vite, and Tailwind CSS for a fast, responsive dark-mode studio UI.
- **Client Rendering:** WebGPU (WGSL compute and fragment shaders) with automatic WebGL2 fallback for 60 FPS retro effects across all desktop and mobile devices.
- **Client State:** Zustand for real-time parameter synchronization without unnecessary component re-renders.
- **Server Framework:** FastAPI with Uvicorn and Pydantic v2, exposing lean endpoints for video export and health checks.
- **Transcoding Core:** Native FFmpeg integration modernized from the current Python codebase, streaming video frames through disk-backed temporary files to prevent OOM errors.
- **Deployment Infrastructure:** Git-driven infrastructure via `wrangler.toml` for Cloudflare Pages and `render.yaml` for Render Web Service.

### Expected Features

**Table Stakes (Must Have for Launch):**
- Drag-and-drop media input for images (PNG, JPG, WebP, GIF) and videos (MP4, WebM).
- Real-time ASCII effect shader with customizable character ramps (Standard, Dense, Simple, Blocks) and scaling controls.
- Color and tone adjustments: Brightness, Contrast, Saturation, Hue Rotation, Gamma, and Invert.
- Viewport interaction: Zoom (`-`, `+`, `100%`, `Reset`) and pan.
- Instant client-side export: PNG, JPEG, SVG, and plain text (`.txt`) ASCII art.
- Studio dark/light UI theme with clean reset actions.

**Differentiators (Competitive Advantage):**
- Full retro shader suite: Dithering (Floyd-Steinberg, Bayer), Halftone dots, VHS/CRT scanlines, Matrix Rain, and Noise Field.
- Live interactive webcam mode piping real-time camera feeds through retro shaders.
- High-fidelity server-side MP4 video and animated GIF export with audio synchronization.
- Half-block double-density character rendering (`\u2580`) preserving dual colors per cell.

**Deferred (v2+):**
- Cloud-synced user workspaces and community preset galleries via Neon PostgreSQL.
- Three.js standalone embeddable 3D HTML export.

### Architecture Approach

A clean split monorepo with `client/` and `server/` directories:
- `client/`: Static SPA deployed to Cloudflare Pages edge network. Runs the WebGPU shader loop, parameter management, and client-side canvas rasterization.
- `server/`: Modernized Python service deployed on Render. Strips obsolete terminal components (`src/terminal.py`), isolates core algorithms (`src/renderer.py`, `src/video.py`, `src/audio.py`), and serves `/api/export/video` and `/api/health`.
- Root manifests: `wrangler.toml` and `render.yaml` automate cloud deployment on every Git push to `main`.

### Critical Pitfalls

1. **Render Free Tier Cold Starts:** Mitigated by keeping all image exports 100% client-side, sending a background `/api/health` wake-up ping when a user selects a video file, and displaying transparent UI progress indicators.
2. **WebGPU Hardware Fragmentation:** Mitigated by detecting adapter support and seamlessly activating WebGL2 shaders when WebGPU is unavailable.
3. **512MB RAM Limits on Render:** Mitigated by streaming frames chunk-by-chunk through FFmpeg pipes and enforcing a 60-second video duration cap for free-tier exports.
4. **Premature Implementation:** Mitigated by utilizing Stitch MCP for iterative UI design review and securing user approval before writing frontend code.

## Implications for Roadmap

Based on the research findings and user requirements, the coarse-grained phase structure should proceed as follows:

### Phase 1: Codebase Modernization & Core Extraction
- **Rationale:** The existing codebase must be audited and streamlined before building web wrappers around it.
- **Delivers:** Cleaned, modernized Python package with terminal-only code archived, core rendering and video routines isolated into clean service modules, and 100% passing tests, linting (`ruff`), and typing (`mypy`).
- **Addresses:** Codebase modernization, removal of dead code, optimization of core math algorithms.
- **Avoids:** Carrying legacy terminal debt into the server architecture.

### Phase 2: Web Studio UI Design & Client Shader Pipeline
- **Rationale:** The interactive studio experience and WebGPU shaders must be designed, prototyped via Stitch MCP, approved by the user, and implemented on the client before hooking up export endpoints.
- **Delivers:** Stitch MCP design contract approved by the user; React + Vite + Tailwind SPA with WebGPU/WebGL2 shader engine (ASCII, dither, halftone, VHS, adjustments), media input (drag-and-drop & webcam), and client-side exports (PNG, JPG, SVG, TXT).
- **Addresses:** UI/UX redesign, real-time client preview, Grainrad feature set.
- **Avoids:** Premature coding without design approval; WebGPU browser fragmentation.

### Phase 3: Backend API, High-Res Export & Git-Driven Deployment
- **Rationale:** Connect the client studio with the Python FastAPI service, integrate heavy FFmpeg video exports, and deploy both tiers via Git-driven configuration.
- **Delivers:** FastAPI endpoints (`/api/export/video`, `/api/health`), chunked video transcoding with audio sync, Neon PostgreSQL scaffolding, and production deployment via `render.yaml` and `wrangler.toml` under $0/month free tier.
- **Addresses:** High-fidelity video export, Git-driven infrastructure, production release.
- **Avoids:** Free-tier OOM crashes, cold-start timeouts, and unexpected infrastructure charges.

## Sources

- Grainrad functional inspection via Playwright browser automation (`https://grainrad.com/`).
- WebGPU and WGSL Official W3C Specifications.
- Cloudflare Pages & Workers Documentation (`wrangler.toml`).
- Render Blueprint Documentation (`render.yaml`).
- Existing codebase architecture and benchmark profiles (`.planning/codebase/`).

---
*Research summary for: RGB ASCII & Retro FX Studio*
*Researched: 2026-11-16*
