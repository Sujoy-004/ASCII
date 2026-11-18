# Phase 3: Backend API, High-Res Export & Git-Driven Deployment - Context

**Gathered:** 2026-11-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the lightweight FastAPI backend service around the modernized core, connect heavy FFmpeg video and animated GIF export with audio synchronization, scaffold zero-cost Neon PostgreSQL persistence, and configure automated Git-driven deployments on Cloudflare and Render at $0/month. Everything needed for the project is completed in v1 (no v2).

</domain>

<decisions>
## Implementation Decisions

### 1. Rendering Architecture & Preview Parity (Critical)
- **D-01:** Hybrid Client Canvas Streaming + Backend FFmpeg Transcode. The browser records rendered WebGPU/WebGL2 canvas frames and streams them in chunks to FastAPI; backend FFmpeg transcodes them into high-res H.264 MP4 or two-pass palettized animated GIF, merging original video audio in tight sync. Preserves 100% pixel-perfect shader parity across all 16 Grainrad shaders while keeping backend RAM under 80MB (well below Render's 512MB limit) without headless browser/Puppeteer overhead or Python shader re-implementation. — **Reversibility:** one-way — Architectural foundation defining client-server export contract and data flow.

### 2. Job Lifecycle & API Contract (Critical)
- **D-02:** Asynchronous Job ID with Short-Polling Lifecycle. API contract: `POST /api/export` creates job and returns job UUID; client polls `GET /api/export/{id}/status` every 1.5s with live progress telemetry; downloads finished file via `GET /api/export/{id}/download`. Immune to Cloudflare/Render 100s HTTP gateway timeouts; periodic status pings keep Render container active to prevent idle spin-down during transcode. — **Reversibility:** costly — Dictates backend routing, job management, and frontend export hooks.

### 3. Export Progress & Waiting Experience (High)
- **D-03:** Multi-Stage Retro Terminal Modal Progress Experience. Client export modal presents multi-stage visual progression ("1/3 Capturing Canvas Frames", "2/3 FFmpeg Encoding", "3/3 Ready for Download") with a live percentage bar, elapsed timer, and retro CRT terminal styling. — **Reversibility:** reversible — Frontend UI styling and state mapping.

### 4. Server Wake-Up & Cold-Start Notice (Medium)
- **D-04:** Intent-Driven Pre-Warm with Header Status Pill. Background `GET /api/health` ping triggers when user drops a video file or opens the Export dialog, masking the 30–45s container cold-start delay during normal creative editing. Ambient status pill (`● Engine: Standby` → `● Engine: Ready`) provides non-intrusive server status in the studio header/inspector; protects Render's 750 free monthly compute hours against bounce visits. — **Reversibility:** reversible — Triggers and UI indicators can be adjusted easily.

### 5. Audio Handling in Video Exports (High)
- **D-05:** Single-Pass Streaming Audio Mux with User Mute Toggle. Uses `-map 1:v:0 -map 0:a:0? -c:a aac -b:a 128k -af "aresample=async=1000" -shortest` to preserve original video audio in tight sync with zero intermediate audio disk files. UI provides `[x] Keep Original Audio (Synced)` toggle in export dialog; automatically mutes (`-an`) for animated GIF exports or when disabled by user. — **Reversibility:** reversible — FFmpeg parameter flags and UI toggle.

### 6. Database & Offline Setup (Medium)
- **D-06:** Stateless Core with Documented Neon Schema Blueprint (All in v1, No v2). Backend operates 100% stateless and anonymous in production; zero database memory footprint on Render. User presets (custom ASCII characters, shader slider presets) persist client-side in browser `localStorage`/`IndexedDB` with full offline support. Complete deliverable includes `docs/database-schema.sql` (defining `users`, `presets`, `tags`) fulfilling `INFRA-03` scaffolding requirement cleanly. User explicitly confirmed: all requirements completed in v1, no v2. — **Reversibility:** costly — Shifts persistence model permanently to client-side storage for v1 with reference SQL schema.

### 7. Security & Resource Limits (Critical)
- **D-07:** Multi-Layer Defensive Guards for Render 512MB RAM Ceiling. Strict boundaries: 60-second maximum video duration, 1080p maximum resolution, 25MB maximum upload payload. `asyncio.Semaphore(1)` concurrency lock ensures only one heavy transcode runs at a time, rejecting concurrent requests with HTTP 503 ("Server busy encoding, retrying...") to guarantee the container never exceeds 512MB RAM. FFmpeg bounded with `-threads 1 -preset ultrafast` and a hard 90s subprocess timeout. — **Reversibility:** reversible — Limits can be tuned in configuration.

### 8. Storage & File Retention (High)
- **D-08:** Hybrid Pipelined Streaming + Scoped Context Cleanup & Janitor Sweeper. Raw pixel frames stream through standard I/O pipes without writing uncompressed frames to disk. Upload and export files are written to request-scoped temporary directories and immediately removed upon download completion via `try...finally`. Background `asyncio` lifespan sweeper runs on boot and every 10 minutes to purge any orphaned `/tmp` files older than 10 minutes, guaranteeing zero disk accumulation. — **Reversibility:** reversible — Tempfile lifecycle management pattern.

### 9. Reliability & Production Operations (High)
- **D-09:** Direct CORS with Git-Driven Blueprints (`render.yaml` & `wrangler.toml`). Frontend deploys to Cloudflare Pages via `wrangler.toml` (`npm run build` targeting `web/dist`); backend deploys to Render via `render.yaml` on native Python runtime with FFmpeg. Direct CORS with regex support for `localhost:5173`, production domain, and Cloudflare Pages preview URLs (`https://*.pages.dev`). — **Reversibility:** costly — Production cloud hosting configurations and deployment pipelines.

### the agent's Discretion
- Internal temporary directory naming conventions and UUID generator for export jobs.
- Exact progress polling interval cadence (1.5s recommended).
- Specific CORS configuration regex strings for branch preview deployments.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Specifications & Governance
- `.planning/PROJECT.md` — Core value, constraints, and architecture decisions
- `.planning/ROADMAP.md` — Phase 3 scope and success criteria (EXPORT-01..04, INFRA-01..04)
- `.planning/REQUIREMENTS.md` — Requirements catalog (EXPORT-01..04, INFRA-01..04)
- `.planning/phases/01-codebase-modernization-core-engine-extraction/01-CONTEXT.md` — Phase 1 decisions (no-Docker, zero-heavy-infra, core engine modules)
- `.planning/phases/02-studio-ui-ux-redesign-client-shader-pipeline/02-CONTEXT.md` — Phase 2 decisions (Three.js WebGPU/TSL shaders, 16 retro effects, client canvas recorder)

### Core Engine & Media Tooling
- `src/video.py` — FFmpeg subprocess invocation, stream piping, and decode error classification
- `src/audio.py` — FFprobe stream probing and audio metadata detection
- `src/sync.py` — Rate, dimension, and duration probing routines
- `src/renderer.py` — Core luminance and character mapping references

### Deployment Blueprints & Scaffolding
- `render.yaml` — Render Blueprint specification for FastAPI web service deployment
- `wrangler.toml` — Cloudflare Pages configuration for React/Vite SPA static edge deployment
- `docs/database-schema.sql` — Neon PostgreSQL schema scaffolding specification

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/video.py`: Subprocess handling patterns, seekable temporary stderr buffering, and termination classification (`classify_decode_termination`).
- `src/audio.py`: `detect_audio_status` via FFprobe for checking whether uploaded video contains audio streams.
- `src/sync.py`: `probe_video_rate`, `probe_video_size`, and `probe_media_duration` for pre-flight validation against 60s/1080p limits.
- `web/src/components/studio/ExportModal.tsx`: Existing export modal to be connected to backend video export API and multi-stage progress UI.
- `web/src/services/exportService.ts`: Existing client-side export utility to be extended with `/api/export` API client.

### Established Patterns
- Zero-heavy-infra / No-Docker constraint (D-02): Standard Python 3.10+ virtualenv / native packages; Render deploys directly via Python environment.
- Single-threaded bounded memory execution under Render 512MB RAM ceiling.
- Hermetic test coverage: Mocked subprocesses and synthetic buffers in `tests/`.

### Integration Points
- `src/api/main.py`: New FastAPI application entry point with `/api/health`, `/api/export`, `/api/export/{id}/status`, `/api/export/{id}/download`.
- `web/src/services/api.ts`: API client with pre-warming healthcheck and job short-polling hook.
- `render.yaml`: Root configuration for Render web service.
- `wrangler.toml`: Root configuration for Cloudflare Pages static edge.
- `docs/database-schema.sql`: Scaffolding document for Neon PostgreSQL schema.

</code_context>

<specifics>
## Specific Ideas

- **All in v1, Zero v2 Scope:** The user explicitly affirmed that there is no v2; all requirements and features are delivered completely in v1.
- **Preview Parity via Hybrid Canvas Streaming:** Rendering 16 WebGPU shaders on a free 512MB CPU server is impossible; client records canvas frames directly and FFmpeg transcodes them with original audio multiplexing.
- **Cold-Start Pre-warming:** Pinging `/api/health` on video load or export panel open hides the 30-45s Render cold start behind normal shader editing time without burning through the 750 free monthly compute hours.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed strictly within phase scope. The user explicitly determined that all planned scope is delivered in v1 with no v2 release planned.

</deferred>

---

*Phase: 3-Backend API, High-Res Export & Git-Driven Deployment*
*Context gathered: 2026-11-18*
