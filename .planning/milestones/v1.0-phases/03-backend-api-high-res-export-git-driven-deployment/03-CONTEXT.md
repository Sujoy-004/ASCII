# Phase 3: Backend API, High-Res Export & Git-Driven Deployment - Context

**Gathered:** 2026-11-18
**Status:** Frozen & Approved for Implementation Planning

<domain>
## Phase Boundary

Build the lightweight FastAPI backend service around the modernized core, connect heavy FFmpeg video and animated GIF export with audio synchronization, scaffold zero-cost Neon PostgreSQL persistence, and configure automated Git-driven deployments on Cloudflare and Render at $0/month. Everything needed for the project is completed in v1 (no v2).

</domain>

<decisions>
## Implementation Decisions

### 1. Rendering Architecture & Preview Parity (D-01)
- **D-01:** Hybrid Canvas Capture, Temporary Backing-Buffer Lock & Controlled Chunk Transport.
  - **DPI Decoupling & Renderer Reuse:** CSS pan/zoom does not affect `canvas.captureStream()`. The actual issue is `window.devicePixelRatio` multiplying internal canvas dimensions. Reuses the existing Three.js renderer by temporarily setting `pixelRatio = 1.0` and resizing to target export dimensions (`1080p` or `720p`), restoring interactive dimensions and device `pixelRatio` upon export completion or cancellation. Avoids spinning up a second WebGPU context.
  - **Parity Definition:** Delivers 1:1 mathematical shader-pipeline parity across all 16 retro effects. Bit-for-bit pixel parity is explicitly not promised due to lossy intermediate and distribution video compression.
  - **Browser Codec Negotiation:** Client negotiates supported codecs: `video/webm;codecs=vp9` → `video/webm;codecs=vp8` → `video/webm` → `video/mp4;codecs=avc1` (for Safari compatibility).
  - **Target Bitrates & Adaptive Duration:** Treats MediaRecorder bitrate as a target rather than a hard guarantee. Target recording bitrate: 3.5 Mbps for 1080p (`videoBitsPerSecond: 3_500_000` → ~26 MB for 60s) and 2.0 Mbps for 720p.
  - **Bounded Chunk Queue & Upload Backpressure:** Bounded client-side queue (max 5 chunks in flight) with sequential uploads. If network latency delays chunk delivery, backpressure pauses recording or sheds non-critical frames before buffer exhaustion. Max 5 MB per individual chunk. Hard cumulative upload ceiling of 35 MB enforced client-side and server-side.
  - — **Reversibility:** one-way — Core client-server export contract and data pipeline foundation.

### 2. Single-Worker Concurrency & Job State Machine (D-02)
- **D-02:** Single-Worker Architecture with In-Memory Concurrency Lock & Fail-Fast Admission.
  - **Single Instance & Worker Constraint:** Render free service is explicitly configured for `numInstances: 1` and Uvicorn `--workers 1`. Concurrency admission uses a clean, process-local `asyncio.Lock()`. Horizontal multi-worker scaling would require external distributed locking (e.g., Redis/DB) and is explicitly documented as out of scope for v1.
  - **Fail-Fast Admission:** Exactly one export job is admitted globally. `POST /api/export/init` acquires the lock; if busy, it returns immediate `HTTP 503 Service Unavailable` with `Retry-After: 30` and `{ "error": "server_busy", "retry_after": 30 }`. No server-side waiting queue in v1.
  - **8-State Machine (Starts in `capturing`):**
    `[capturing]` → `[uploading]` → `[encoding]` → `[completed]` (terminal states: `failed`, `cancelled`, `expired`).
  - **Container Restart Resilience:** When client polls `GET /api/export/{id}/status`, an unknown job ID returns `HTTP 404` with state `expired` and `{ "state": "expired", "message": "Server instance restarted or job expired. Please retry." }`, allowing the UI to trigger a clean retry.
  - — **Reversibility:** costly — Dictates backend routing, job management, and frontend export hooks.

### 3. Four-Stage Observable Telemetry (D-03)
- **D-03:** Multi-Stage Measurable Telemetry (No Fabricated Progress Curves).
  - **Stage 1 (Canvas Frame Capture):** Measured client-side by `capturedFrames / totalTargetFrames` (0–100%).
  - **Stage 2 (Chunk Upload):** Measured by `uploadedBytes / totalRecordedBytes` via `XHR.upload.onprogress` (0–100%).
  - **Stage 3 (FFmpeg Encoding):** Measured server-side by parsing FFmpeg `-progress pipe:1` stdout lines (`out_time_us / target_duration_us`, with live `fps` and `speed` metrics).
  - **Stage 4 (Ready for Download):** Download button, file size, and 10-minute expiration countdown timer.
  - — **Reversibility:** reversible — Frontend UI styling and state mapping.

### 4. Intent-Driven Pre-Warming & Polling Cadence (D-04)
- **D-04:** Intent-Driven Pre-Warm with Exponential Backoff Health Polling.
  - `GET /api/health` triggers only when user explicitly opens the Server Export dialog or selects MP4/Server-GIF format.
  - Client polling during container wake-up uses exponential backoff (`0s → 3s → 7s → 13s → 21s → 31s → 45s → 60s`), staying strictly within the backend's 30 req/min healthcheck rate limit.
  - Status pill displays `● Engine: Standby` → `● Engine: Waking up (~30s)...` → `● Engine: Ready`.
  - — **Reversibility:** reversible — Trigger conditions and UI indicators.

### 5. Audio Graph & Reusable Nodes (D-05)
- **D-05:** Reusable Web Audio Graph with Persistent Node Reuse & Fallback Route.
  - **Persistent Web Audio Graph:** In `web/src/store/useStudioStore.ts`, creates and reuses a single `MediaElementAudioSourceNode` for the persistent `<video>` element (`registeredVideo`) to prevent browser `InvalidStateError`.
  - **Dual-Destination Audio Routing:**
    `[<video>]` → `[Persistent MediaElementAudioSourceNode]` → `[GainNode]`
    ├──► `AudioContext.destination` (User speakers remain audible during export)
    └──► `createMediaStreamDestination()` → Audio track added to `canvas.captureStream()`.
  - **Autoplay Compliance:** `audioContext.resume()` is called directly inside the user's "Start Export" click interaction.
  - **Source File Preservation:** The original uploaded `File` object is retained in non-reactive storage (`activeFile` in `useStudioStore.ts`) so the server-side audio fallback can read and upload it.
  - **Server-Side Audio Fallback Endpoint:** Dedicated route `POST /api/export/{id}/source-audio` accepts source media with `X-Clip-Start` and `X-Clip-Duration` headers, using pre-input `-ss` seeking:
    `ffmpeg -ss <start> -t <duration> -i source_media -i assembled_canvas.webm -map 1:v:0 -map 0:a:0? -c:v copy -c:a aac -b:a 192k -af "aresample=async=1:first_pts=0" -shortest output.mp4`
  - **Webcam Microphone Opt-In:** Webcam audio requires explicit checkbox opt-in `[ ] Include Microphone Audio`.
  - **Animated GIFs:** Strictly silent (`-an` enforced; audio routing bypassed).
  - — **Reversibility:** reversible — FFmpeg parameter flags and Web Audio graph wiring.

### 6. Stateless Architecture with Documented SQL Scaffolding (D-06)
- **D-06:** Stateless Backend with Documented SQL Blueprint (All in v1, No v2).
  - Zero database runtime overhead; no `SQLAlchemy`, `asyncpg`, or `alembic` dependencies in `pyproject.toml`.
  - Standalone SQL reference schema at `docs/database-schema.sql` defining relational tables for future reference without active runtime database initialization.
  - User presets and settings persist in browser `localStorage`.
  - — **Reversibility:** costly — Shifts persistence model to client-side storage for v1.

### 7. Resource Limits, Container Assembly Validation & Benchmarking (D-07)
- **D-07:** Defensive Resource Limits, Full Container Assembly Validation & 0.1 vCPU Benchmark.
  - **Provisional Video Limits:** Max 60.0s duration, 1080p max resolution, 30 FPS for 1080p (up to 60 FPS for <=720p), total pixel budget 3.73 × 10⁹ pixel-frames.
  - **Stricter Animated GIF Limits:** Max 15.0s duration, 720p max resolution, 15 FPS max (10–12 FPS typical), total pixel budget 0.20 × 10⁹ pixel-frames.
  - **Payload Ceilings:** Max 35 MB total chunks for video, max 20 MB for GIF. Max 5 MB per individual chunk. Max output file size: 50 MB for MP4, 25 MB for GIF.
  - **Full Container Assembly Validation:** Chunks stream to disk and are assembled into a single file before running `ffprobe` container inspection. Raw individual chunks are never inspected in isolation.
  - **Benchmark Environment Plan (`bench_export.py`):** Pinned to **512 MB RAM** and **0.1 vCPU** (matching Render free tier). Measures complete process tree RSS (`Python Uvicorn parent + FFmpeg child processes`). Pass criteria: Peak RSS < 250 MB; 30s 1080p encode finishes within 75 seconds.
  - — **Reversibility:** reversible — Parameter limits and benchmark verification.

### 8. Storage Lifecycle, Active State Protection & Quota Defense (D-08)
- **D-08:** Ephemeral Storage Lifecycle with Active State Protection.
  - **Separated Timers:**
    - Upload Inactivity Timeout: 60 seconds (aborts job if no chunk received while in `capturing`/`uploading`).
    - FFmpeg Subprocess Timeout: 90 seconds (hard process kill).
    - Maximum Job Lifetime: 10 minutes total (from `init` to transcode complete).
    - Artifact Retention: 10 minutes post-completion, with 5-minute retry grace period after first download.
  - **Active Process Protection:** Janitor sweeper runs every 60s. It strictly never purges directories for jobs in active states (`capturing`, `uploading`, `encoding`), verifying both in-memory job state and OS process table PID before removing files.
  - **Disk Quota Ceiling:** Max 500 MB for `/tmp/ascii_studio_exports/`. If usage exceeds 400 MB, completed jobs older than 2 minutes are purged immediately.
  - — **Reversibility:** reversible — Cleanup scheduling and directory management.

### 9. Hardened Production CORS (D-09)
- **D-09:** Hardened CORS with Strict Cloudflare Preview Matching.
  - Allowed Origins: `https://rgb-ascii.pages.dev`, `http://localhost:5173`, `http://127.0.0.1:5173`, and regex `^https:\/\/[a-zA-Z0-9-]+\.rgb-ascii\.pages\.dev$`.
  - Allowed Headers: `Content-Type`, `X-Job-Token`, `X-Turnstile-Token`, `X-Clip-Start`, `X-Clip-Duration`.
  - Exposed Headers: `Content-Disposition`, `Content-Length`, `Retry-After`, `X-Job-Token`.
  - Allowed Methods: `GET`, `POST`, `OPTIONS`.
  - — **Reversibility:** costly — Production deployment and edge routing configuration.

### 10. Anonymous API Abuse Prevention & Ingress Security (D-10)
- **D-10:** Ingress Abuse Defense, Validated Proxy Headers & Short-Lived Download Tokens.
  - **Validated Proxy IP Extraction:** `CF-Connecting-IP` is trusted only after validating that the request originated from published Cloudflare IP address ranges (CIDR blocks). `X-Forwarded-For` is never blindly trusted.
  - **Header-Based Job Secret Tokens:** State updates, chunk uploads, and status checks require `X-Job-Token: <token>` header (generated via `secrets.token_urlsafe(32)`).
  - **Short-Lived Single-Use Download Tokens:** When an export completes, the server generates a separate short-lived download token (TTL 5 minutes): `GET /api/export/{id}/download?download_token=<short_token>`. The master job secret token is never exposed in download links or browser URLs.
  - **Mandatory Turnstile in Production:** If `ENVIRONMENT=production`, missing Turnstile configuration (`TURNSTILE_SECRET_KEY` / `TURNSTILE_SITE_KEY`) causes an explicit server startup error unless `TURNSTILE_DISABLED=true` is explicitly set. Turnstile is gracefully bypassed in local development (`localhost`).
  - **Per-IP Rate Limits (via `slowapi`):** Max 3 inits / 5 min; max 120 chunk uploads / min; max 60 status polls / min; max 30 health pings / min. Strictly 1 active job per IP.
  - — **Reversibility:** costly — Ingress security, proxy authentication, and token issuance.

### the agent's Discretion
- Internal directory structure under `/tmp/ascii_studio_exports/{job_id}/`.
- Exact backpressure threshold in client chunk queue (3–5 chunks).
- Format-specific FFmpeg CRF fine-tuning (`crf=23` default for H.264).

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
- `render.yaml` — Render Blueprint specification for FastAPI web service deployment (`numInstances: 1`, `--workers 1`)
- `wrangler.toml` — Cloudflare Pages configuration for React/Vite SPA static edge deployment
- `docs/database-schema.sql` — Neon PostgreSQL schema scaffolding specification

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/video.py`: Subprocess handling patterns, seekable temporary stderr buffering, and termination classification (`classify_decode_termination`).
- `src/audio.py`: `detect_audio_status` via FFprobe for checking whether uploaded video contains audio streams.
- `src/sync.py`: `probe_video_rate`, `probe_video_size`, and `probe_media_duration` for pre-flight validation against 60s/1080p limits.
- `web/src/store/useStudioStore.ts`: Persistent `<video>` element (`registeredVideo`) and non-reactive media storage (`activeFile`, `activeObjectUrl`, `activeStream`).
- `web/src/engine/Renderer.ts`: `StudioRenderer` with `setSize` and `setPixelRatio` controls.
- `web/src/engine/Pipeline.ts`: `StudioPipeline` with `resize` method.
- `web/src/export/videoExport.ts`: Existing `recordWebmClip` and `recordGifClip` client recording utilities.
- `web/src/components/panels/ExportDrawer.tsx`: Export tab interface to be wired to the server export modal.

### Established Patterns
- Zero-heavy-infra / No-Docker constraint (D-02): Standard Python 3.10+ virtualenv / native packages; Render deploys directly via Python environment.
- Single-worker bounded memory execution under Render 512MB RAM ceiling.
- Hermetic test coverage: Mocked subprocesses and synthetic buffers in `tests/`.

### Integration Points
- `src/api/main.py`: FastAPI application entry point.
- `src/api/routes/export.py`: Export endpoints (`init`, `chunk`, `source-audio`, `finalize`, `status`, `cancel`, `download`).
- `src/api/jobs.py`: In-memory `asyncio.Lock` job registry, 8-state machine, and download token manager.
- `src/api/janitor.py`: Background storage cleanup sweeper with active process protection.
- `src/api/security.py`: Cloudflare proxy IP validator, rate limiter, and Turnstile verifier.
- `web/src/services/exportApi.ts`: Client API client with chunk sequencer, backpressure queue, and polling hook.
- `web/src/components/modals/ServerExportModal.tsx`: Four-stage retro terminal progress modal.
- `render.yaml`: Root configuration for Render web service (`numInstances: 1`, Uvicorn `--workers 1`).
- `wrangler.toml`: Root configuration for Cloudflare Pages static edge.
- `docs/database-schema.sql`: Scaffolding document for Neon PostgreSQL schema.

</code_context>

<specifics>
## Specific Ideas

- **All in v1, Zero v2 Scope:** The user explicitly affirmed that there is no v2; all requirements and features are delivered completely in v1.
- **Render Free Reality:** Render Free is treated as a prototype/public-beta deployment. Its 0.1 shared CPU allocation is the dominant constraint, meaning single-thread fast encoding (`-preset ultrafast`) and strict duration limits are paramount.
- **Web Audio Node Reuse:** Creating `MediaElementAudioSourceNode` repeatedly on the same video element causes an uncatchable browser `InvalidStateError`. Creating it once and keeping it permanently attached to the persistent `<video>` element guarantees robust audio capture across multiple exports.
- **Short-Lived Download Tokens:** Main job secret token is never placed in the `href` download URL; the client requests or receives a 5-minute single-use download token upon completion.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed strictly within phase scope. The user explicitly determined that all planned scope is delivered in v1 with no v2 release planned.

</deferred>

---

*Phase: 3-Backend API, High-Res Export & Git-Driven Deployment*
*Context gathered: 2026-11-18 (Frozen & Approved)*
