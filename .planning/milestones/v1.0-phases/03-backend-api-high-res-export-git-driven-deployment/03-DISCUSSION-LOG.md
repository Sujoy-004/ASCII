# Phase 3: Backend API, High-Res Export & Git-Driven Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered and final amendments.

**Date:** 2026-11-18
**Phase:** 3-Backend API, High-Res Export & Git-Driven Deployment
**Status:** Frozen & Approved for Implementation Planning
**Areas discussed:** Rendering Architecture & Preview Parity, Job Lifecycle & API Contract, Export Progress & Waiting Experience, Server Wake-Up & Cold-Start Notice, Audio Handling in Video Exports, Database & Offline Setup, Security & Resource Limits, Storage & File Retention, Reliability & Production Operations, Ingress Security & Abuse Prevention

---

## Final Amendments & Architecture Freeze

The user approved the architecture specification in principle and mandated the following 5 technical amendments, now frozen in `03-CONTEXT.md`:

1. **D-01 (Canvas Capture & Chunk Transport):**
   - Clarified that CSS pan/zoom does not affect `canvas.captureStream()`; `devicePixelRatio` multiplying backing-buffer dimensions is the real issue.
   - Decoupled export dimensions and locked `pixelRatio = 1.0` temporarily on the existing Three.js renderer, avoiding secondary WebGPU context creation.
   - Added bounded client-side chunk queue (max 5 chunks) with backpressure to pause capture if upload lags.
   - Max 5 MB individual chunk limit; hard cumulative upload ceiling of 35 MB.
   - Target bitrate: 3.5 Mbps for 1080p, 2.0 Mbps for 720p, treated as targets rather than hard guarantees.
2. **D-02 (Single-Worker Concurrency & Lock):**
   - Explicitly configured 1 Render instance and 1 Uvicorn worker (`numInstances: 1`, `--workers 1`).
   - Clean process-local `asyncio.Lock()` used for single global export admission.
   - Immediate `HTTP 503` fail-fast rejection with `Retry-After: 30` when busy (no waiting queue in v1).
   - Starts directly in state `capturing`.
3. **D-05 (Audio Graph & File Preservation):**
   - Persistent `MediaElementAudioSourceNode` created once and reused on the persistent `<video>` element, preventing browser `InvalidStateError`.
   - Original `File` object retained in non-reactive store for server-side audio fallback.
   - Added dedicated fallback route `POST /api/export/{id}/source-audio` with `-ss` pre-seeking.
   - Explicit opt-in checkbox for webcam microphone audio; GIFs strictly silent (`-an`).
4. **D-08 (Retention & Active State Protection):**
   - Maximum job lifetime increased from 5 to 10 minutes.
   - Separated timeouts: Upload inactivity (60s), FFmpeg transcode (90s), Artifact retention (10m).
   - Janitor sweeper strictly protects active states (`capturing`, `uploading`, `encoding`) and verifies process PID before purging.
5. **D-10 (Anonymous Abuse Prevention & Ingress Security):**
   - `CF-Connecting-IP` trusted strictly after validating origin from published Cloudflare proxy IP CIDRs.
   - `X-Forwarded-For` never blindly trusted.
   - Missing Turnstile configuration in production causes explicit startup failure unless `TURNSTILE_DISABLED=true`.
   - Main job secret token kept in request headers (`X-Job-Token`); download URL uses a separate short-lived single-use download token (TTL 5m).

---

## the agent's Discretion

- Internal directory structure under `/tmp/ascii_studio_exports/{job_id}/`.
- Exact backpressure threshold in client chunk queue (3–5 chunks).
- Format-specific FFmpeg CRF fine-tuning (`crf=23` default for H.264).

## Deferred Ideas

None — discussion stayed strictly within phase scope. The user explicitly determined that all planned scope is delivered in v1 with no v2 release planned.
