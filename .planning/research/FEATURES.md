# Feature Research

**Domain:** Browser-Based Visual Effects & Retro ASCII Generator
**Researched:** 2026-11-16
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features identified from Grainrad inspection and retro creative tools. Missing these makes the studio feel incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-Media Input (Drag & Drop) | Users want to test their own assets immediately | MEDIUM | Support PNG, JPG, WebP, GIF, MP4, WebM; auto-detect aspect ratio |
| Real-Time Interactive Canvas Preview | Immediate visual feedback when adjusting parameters | HIGH | Canvas/WebGPU viewport with zoom (`-`, `+`, `100%`, `Reset`) and pan |
| ASCII Core Shader & Presets | Core value proposition; must offer character ramps | MEDIUM | Scale, spacing, output width, character presets (Standard, Simple, Dense, Blocks) |
| Color & Tone Adjustments | Raw media often requires contrast/gamma boost for good ASCII | LOW | Sliders for Brightness, Contrast, Saturation, Hue Rotation, Gamma, and Invert |
| Instant Client-Side Image/Text Export | Artists want immediate access to stylized outputs | LOW | 1-click export to PNG, JPEG, SVG, and plain text (`.txt`) ASCII |
| Dark/Light Studio Theme | Visual artists require low-distraction creative environments | LOW | Dark-first studio layout with high-contrast UI controls and clean reset actions |

### Differentiators (Competitive Advantage)

Features that elevate the project into an advanced visual effects workstation.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Diverse Retro Shader Modes | Expands beyond ASCII to full retro aesthetic toolkit | HIGH | Dithering (Floyd-Steinberg, Bayer), Halftone dots, Matrix Rain, VHS scanlines, Pixel Sort, Crosshatch, Voronoi |
| Live Webcam Processing | Engaging interactive demo; allows users to see themselves as ASCII/retro art | MEDIUM | Browser `navigator.mediaDevices.getUserMedia` piped directly to shader texture |
| Server-Side High-Res Video Export | Client browsers struggle with long 1080p video exports | HIGH | FastAPI + FFmpeg backend exports high-bitrate MP4 and animated GIF with audio sync |
| Three.js / HTML Export | Allows web developers to embed interactive retro scenes directly into their sites | MEDIUM | Exports self-contained single-file HTML bundle with Three.js shader runtime |
| Half-Block Double-Density Color Mode | Unique ASCII rendering method from existing engine | LOW | Preserves 2 colors per character cell (`\u2580`), doubling vertical color resolution |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Compulsory User Auth / Signup Wall | Collect user emails | Blocks immediate creativity, creates churn, requires database maintenance | Fully functional anonymous playground; state stored in browser `localStorage` |
| Server-Side Preview Rendering | Guarantees exact server-side match | Consumes expensive server CPU cycles on every slider drag; overruns Render free tier | Client-side WebGPU/Canvas preview for 60fps interaction; backend only on export |
| Unbounded Video File Uploads | Users want to upload 2-hour movies | Fills server disk, triggers HTTP timeouts and Render 512MB RAM OOM crashes | Enforce client-side file length cap (e.g. 60-90 seconds max for free export) |
| Native Desktop Wrapper (Electron) | "Native app" feel | 150MB bundle, OS signing headaches, separate update channels | Progressive Web App (PWA) installable directly from browser with offline caching |

## Feature Dependencies

```
[Media Input: Image / Video / Webcam]
    └──feeds──> [Canvas / WebGPU Render Pipeline]
                     ├──applies──> [Color & Tone Adjustments]
                     ├──applies──> [Active Retro Effect: ASCII / Dither / Halftone / VHS]
                     └──outputs──> [Interactive Viewport]
                                        ├──client export──> [PNG / JPEG / SVG / TXT]
                                        └──backend export──> [FastAPI + FFmpeg MP4 / GIF]
```

### Dependency Notes

- **Render Pipeline requires Media Input:** Textures cannot initialize until an image, video file, or webcam stream is decoded into a frame buffer.
- **Backend Export requires Parameter Serialization:** The client must serialize the exact active settings (effect type, scale, character set, color adjustments) as JSON payload to `/api/export/video`.
- **High-Res Video Export requires FFmpeg:** Render backend requires FFmpeg binary on PATH to execute transcoding and audio muxing.

## MVP Definition

### Launch With (v1)

Minimum viable product to modernize the codebase and deliver a complete, deployed web studio.

- [ ] Modernized, clean Python backend with dead terminal code removed and FastAPI endpoints established.
- [ ] Responsive Web Studio UI designed with Stitch MCP and reviewed by user.
- [ ] Core ASCII effect + Dithering + Halftone + VHS shader modes with parameter sliders.
- [ ] Image (PNG/JPG) and Video (MP4) drag-and-drop input handling.
- [ ] Live webcam video input mode.
- [ ] Client-side export: PNG, JPEG, SVG, Text (`.txt`).
- [ ] Backend export: MP4 video and animated GIF with audio retention.
- [ ] Git-driven $0/month deployment on Cloudflare Pages (`wrangler.toml`) and Render (`render.yaml`).

### Add After Validation (v1.x)

- [ ] Additional shader modes: Matrix Rain, Voronoi, Wave Lines, Pixel Sort.
- [ ] Three.js self-contained HTML export bundle.
- [ ] Preset library (save/load favorite effect configurations in localStorage).

### Future Consideration (v2+)

- [ ] Cloud-synced user presets and project gallery powered by Neon PostgreSQL.
- [ ] Collaborative multi-user canvas sessions.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Drag-and-drop image/video input | HIGH | LOW | P1 |
| Real-time ASCII and Halftone shaders | HIGH | MEDIUM | P1 |
| Color, Brightness & Contrast controls | HIGH | LOW | P1 |
| Client-side PNG, JPG, TXT export | HIGH | LOW | P1 |
| Backend MP4 video export with audio | HIGH | MEDIUM | P1 |
| Cloudflare + Render deployment | HIGH | MEDIUM | P1 |
| Live webcam feed processing | MEDIUM | LOW | P2 |
| Dithering, VHS, Matrix Rain shaders | MEDIUM | MEDIUM | P2 |
| SVG vector export | MEDIUM | MEDIUM | P2 |
| Neon DB cloud user persistence | LOW | HIGH | P3 (Deferred) |

---
*Feature research for: Browser-Based Visual Effects & Retro ASCII Generator*
*Researched: 2026-11-16*
