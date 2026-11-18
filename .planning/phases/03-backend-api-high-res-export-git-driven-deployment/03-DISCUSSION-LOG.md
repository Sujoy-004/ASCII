# Phase 3: Backend API, High-Res Export & Git-Driven Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-18
**Phase:** 3-Backend API, High-Res Export & Git-Driven Deployment
**Areas discussed:** Rendering Architecture & Preview Parity, Job Lifecycle & API Contract, Export Progress & Waiting Experience, Server Wake-Up & Cold-Start Notice, Audio Handling in Video Exports, Database & Offline Setup, Security & Resource Limits, Storage & File Retention, Reliability & Production Operations

---

## Rendering Architecture & Preview Parity (Critical)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Hybrid Client Canvas Streaming + Backend FFmpeg Transcode | Browser renders exact frames, FastAPI + FFmpeg encodes high-res MP4/GIF with audio sync | ✓ |
| Backend Headless Browser Capture (Puppeteer) | Autonomous server render (requires dedicated container with >2GB RAM) | |
| Python Shader Reimplementation | Rewrite all 16 shaders in Python CPU math (risk of visual drift and CPU timeouts) | |
| Python Core ASCII-Only Pipeline | Export plain ASCII terminal video only (drops CRT, Dither, Halftone, and other 15 shaders) | |

**User's choice:** Hybrid Client Canvas Streaming + Backend FFmpeg Transcode
**Notes:** User emphasized Area 5 as the single most critical decision to get right before writing any backend endpoints. Browser renders 16 WebGPU/WebGL2 shaders with 1:1 visual parity; server runs FFmpeg encoding under Render's 512MB RAM ceiling.

---

## Job Lifecycle & API Contract (Critical)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Asynchronous Job ID with Short-Polling | POST job, poll status every 1.5s with live progress bar, download on completion | ✓ |
| Synchronous Direct Download | Single POST request (risks 100s proxy timeout on videos >15s, no progress percentages) | |
| Server-Sent Events (SSE) Stream | Persistent streaming connection (risk of edge proxy buffering and stalled progress updates) | |

**User's choice:** Asynchronous Job ID with Short-Polling
**Notes:** Short-polling avoids Cloudflare/Render 100-second HTTP gateway timeouts and keeps the free-tier container awake while rendering.

---

## Export Progress & Waiting Experience (High)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Multi-Stage Retro Terminal Modal | Shows clear stages (Frame Capture, Encoding, Finalizing) with live percentage and timer | ✓ |
| Simple Standard Progress Bar | Minimalist 0-100% bar without stage breakdown | |
| Indeterminate Loading Spinner | Simple spinning indicator with cancel button | |

**User's choice:** Multi-Stage Retro Terminal Modal
**Notes:** Provides transparent progress feedback across local capture, upload, FFmpeg transcode, and download stages in a styled retro terminal aesthetic.

---

## Server Wake-Up & Cold-Start Notice (Medium)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Intent-Driven Pre-Warm | Quietly wakes server when video is loaded or export tab opened, with subtle status pill | ✓ |
| On-Demand Modal | Only wakes server when Export button is clicked, with a 30-45s countdown notice | |
| Proactive Eager Pre-Warm | Wakes server immediately on page load (risks exhausting 750 monthly free hours) | |

**User's choice:** Intent-Driven Pre-Warm
**Notes:** Pings `/api/health` on video ingestion or export tab open, masking the 30-45s cold start during normal creative shader adjustments while conserving the 750 free monthly compute hours.

---

## Audio Handling in Video Exports (High)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Single-Pass Streaming Mux with Mute Toggle | Automatic audio sync with a user toggle in export options (auto-mutes GIFs) | ✓ |
| Always Mute Video Exports | All exported videos are silent retro clips without audio | |
| Two-Step Secondary Audio Merge | Render silent video first, then stitch audio in a second pass (slower, extra disk I/O) | |

**User's choice:** Single-Pass Streaming Mux with Mute Toggle
**Notes:** Preserves original soundtrack in sync using `aresample=async=1000`; user toggle allows muting; auto-mutes for GIF exports.

---

## Database & Offline Setup (Medium)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Stateless Core + Documented Neon Schema Blueprint | Presets save in browser storage, backend stays 100% stateless with documented SQL schema for v2 | ✓ |
| Pluggable Active ORM (SQLAlchemy) | Active database models in backend code with soft-fail if DB URL is absent | |
| Local SQLite Fallback | Local database file for anonymous job tracking | |

**User's choice:** Option 1 (Stateless Core + Documented Neon Schema Blueprint) with explicit directive: "all will be done in v1, no v2".
**Notes:** User emphasized that for an anonymous export service, storing uploaded videos in a database is unnecessary. Preset persistence runs in browser storage; database schema blueprint satisfies INFRA-03 cleanly.

---

## Security & Resource Limits (Critical)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Multi-Layer Defensive Guards | 60s duration cap, 25MB upload limit, and single concurrency lock to prevent OOM crashes | ✓ |
| In-Memory Sequential Waiting Queue | Queue concurrent exports sequentially in memory | |
| Open Processing | No duration or concurrency limits (high risk of container crash) | |

**User's choice:** Multi-Layer Defensive Guards
**Notes:** Protects Render's 512MB RAM ceiling via `asyncio.Semaphore(1)`, 60-second video length limit, and 25MB upload cap.

---

## Storage & File Retention (High)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Hybrid Pipelined Streaming + Scoped Cleanup & Janitor Sweeper | Immediate delete on download plus automatic 10-minute cleanup for abandoned files | ✓ |
| Immediate Cleanup Only | Delete files only on completed downloads (orphaned files linger if client disconnects) | |
| Pure In-Memory | Hold all video data in RAM (severe crash risk on 512MB containers) | |

**User's choice:** Hybrid Pipelined Streaming + Scoped Cleanup & Janitor Sweeper
**Notes:** Media frames pipe without disk buffering; request tempfiles cleaned up on delivery; background sweeper purges abandoned artifacts.

---

## Reliability & Production Operations (High)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Direct CORS with Git-Driven Config | Cloudflare Pages + Render blueprints (render.yaml, wrangler.toml) with clean preview CORS | ✓ |
| Cloudflare Edge Proxy Gateway | Route all API calls through Cloudflare Functions (risks 100MB upload truncation) | |
| Third-Party Observability | External monitoring service (adds third-party accounts and complexity) | |

**User's choice:** Direct CORS with Git-Driven Config
**Notes:** Dual Git-driven deployment via `render.yaml` (Render Python + FFmpeg) and `wrangler.toml` (Cloudflare Pages SPA) at $0/month.

---

## the agent's Discretion

- Internal job UUID formatting and temp directory path conventions.
- Exact progress polling intervals (1.5s cadence).
- Specific CORS configuration regex strings for branch preview deployments.

## Deferred Ideas

None — discussion stayed strictly within phase scope. The user explicitly determined that all planned scope is delivered in v1 with no v2 release planned.
