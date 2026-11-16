# Pitfalls Research

**Domain:** Browser-Based GPU Visual Effects & Edge/Cloud Deployment
**Researched:** 2026-11-16
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Render Free Tier Cold-Start Latency (Spun-Down Service)

**What goes wrong:**
Render's free tier spins down web services after 15 minutes of inactivity. When a user requests a video export after the backend has slept, the initial request takes 50–70 seconds to boot the container, often resulting in client timeout errors or user frustration.

**Why it happens:**
Free cloud tiers economize resources by hibernating inactive containers.

**How to avoid:**
1. Maintain client-side autonomy: All image exports (PNG, JPEG, SVG, Text) and real-time previews happen 100% on the client with zero backend dependency.
2. Background pre-warming: As soon as a user selects a video file for editing, the web client sends a non-blocking `GET /api/health` ping to awaken the Render instance in the background while the user is still tweaking settings.
3. Informative UI state: When an export is submitted, if the backend is waking up, show a friendly progress spinner: *"Warming up high-resolution video engine (free tier cold-start: ~40s)..."*.

**Phase to address:** Phase 3 (Backend Integration & Deployment).

---

### Pitfall 2: WebGPU Browser & Hardware Fragmentation

**What goes wrong:**
Assuming WebGPU is universally supported leads to blank canvas screens on Firefox (without nightly flags), older Safari versions, or Windows/Linux machines with outdated GPU drivers.

**Why it happens:**
WebGPU is modern and actively rolling out, but not 100% ubiquitous across all legacy hardware and mobile browsers.

**How to avoid:**
Implement an explicit fallback adapter:
1. Probe `navigator.gpu?.requestAdapter()`.
2. If successful, initialize the WebGPU WGSL pipeline.
3. If null or rejected, fall back to WebGL2 GLSL fragment shaders or optimized 2D Canvas context.
4. Display a subtle status indicator in the UI: *"Engine: WebGPU (Hardware Accelerated)"* or *"Engine: WebGL2 (Compatibility Mode)"*.

**Phase to address:** Phase 2 (Client Shader Pipeline).

---

### Pitfall 3: Render Free Tier RAM Exhaustion (OOM Crash at 512MB)

**What goes wrong:**
Processing high-resolution video files (1080p/4K) in Python by reading entire uncompressed video streams into memory causes memory spikes over 512MB, triggering an instant SIGKILL (Exit 137) on Render free tier.

**Why it happens:**
A single second of uncompressed 1080p 60fps RGB24 frames is ~373 MB of raw byte data. Buffering multiple frames in memory exceeds 512MB immediately.

**How to avoid:**
1. Stream frames through FFmpeg pipes or disk-backed temporary files with bounded buffer sizes (process frame-by-frame or chunk-by-chunk).
2. Set client-side validation limits on maximum uploaded video duration (e.g., 60 seconds max for free-tier rendering).
3. Ensure Python temporary files are garbage-collected and unlinked immediately in a `try...finally` block.

**Phase to address:** Phase 1 (Codebase Modernization) & Phase 3 (Backend API).

---

### Pitfall 4: Browser GPU Texture & Video Memory Leaks

**What goes wrong:**
Continuously uploading video frames or webcam feeds to WebGPU textures without explicit lifecycle management leaks GPU memory, causing browser tabs to crash with WebGPU context lost (`GPUDevice.lost`).

**Why it happens:**
Browser garbage collection does not instantly release GPU VRAM buffers allocated by `createTexture()` or `importExternalTexture()`.

**How to avoid:**
1. Reuse static texture allocations for continuous webcam/video streams rather than instantiating new textures every frame.
2. Use `copyExternalImageToTexture` or `importExternalTexture` properly within the `requestAnimationFrame` render loop.
3. Cleanly call `.destroy()` on obsolete GPU buffers when switching media inputs.

**Phase to address:** Phase 2 (Client Shader Pipeline).

---

### Pitfall 5: Premature Implementation Before UI/UX Approval

**What goes wrong:**
Writing complex frontend React components and state structures before aligning on the visual design contract requires painful code rewrites and wasted tokens.

**Why it happens:**
Rushing to code before visual layout, responsive hierarchy, and palette themes are verified.

**How to avoid:**
Strict adherence to the GSD and user-defined approval gate: Use Stitch MCP to generate design prototypes, review them with the user, and require explicit approval before writing frontend UI code.

**Phase to address:** Phase 2 (UI/UX Design Review).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Inlining shaders as giant JavaScript strings | Quick setup | No syntax highlighting, hard to test, error-prone | Never; use `.wgsl` and `.glsl` file imports via Vite plugins |
| Polling backend export status in tight loop | Simple frontend code | Saturates free-tier connection limits | Use progressive backoff polling (e.g. 1s, 2s, 3s) |
| Hardcoding external service URLs | Fast local development | Breaks during production deployment | Use environment variables (`VITE_API_URL` and `render.yaml` env vars) |

---
*Pitfalls research for: Browser-Based GPU Visual Effects & Edge/Cloud Deployment*
*Researched: 2026-11-16*
