# Phase 2: Studio UI/UX Redesign & Client Shader Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-17
**Phase:** 2-Studio UI/UX Redesign & Client Shader Pipeline
**Areas discussed:** Grainrad Intelligence & Engine Foundation, Product Scope & Feature Parity, Studio Workspace & Interaction Design, Media Ingestion & Lifecycle, Shader Architecture & Performance Strategy, Effect Graph & ASCII Creative Engine, Export Capabilities & Acceptance Criteria

---

## 1. Grainrad Intelligence Extraction & Core Engine Foundation

| Option | Description | Selected |
|--------|-------------|:--------:|
| Option A: Three.js WebGPU / TSL Foundation | Match Grainrad's proven stack with built-in WebGPU/WebGL fallback and WGSL support | ✓ |
| Option B: Vanilla Raw WebGPU + WebGL2 | Pure bespoke canvas pipeline with zero framework dependencies (dual WGSL + GLSL shaders) | |
| Option C: Pixi.js v8 Pipeline | 2D WebGPU engine focused on high-performance sprite/text rendering | |

**User's choice:** Option A: Three.js WebGPU Foundation — Match Grainrad's proven stack with built-in WebGPU/WebGL fallback and WGSL support
**Notes:** Playwright MCP live inspection of `grainrad.com` confirmed Three.js WebGPU and WGSL fragment shaders running in production.

---

## 2. Product Scope & Feature Parity (v1 Boundary)

| Option | Description | Selected |
|--------|-------------|:--------:|
| Option A: Strict Core Retro Parity | ASCII, Dithering (Bayer/Floyd-Steinberg), Halftone, and VHS/CRT only | |
| Option B: Core Parity + Extended Fan-Favorites | ASCII, Dithering, Halftone, VHS/CRT, plus Matrix Rain & Pixel Sort | |
| Option C: Full 16-Shader Grainrad Parity | Implement all 16 Grainrad shaders upfront in v1 | ✓ |

**User's choice:** Option C: Full 16-Shader Grainrad Parity — Implement all 16 Grainrad shaders upfront in v1
**Notes:** Full 16 shaders committed for v1: ASCII, Dithering, Halftone, Matrix Rain, Dots, Contour, Pixel Sort, Blockify, Threshold, Edge Detection, Crosshatch, Wave Lines, Noise Field, Voronoi, VHS, plus global Tone Adjustments.

---

## 3. Studio Workspace & Interaction Design

| Option | Description | Selected |
|--------|-------------|:--------:|
| Option A: Three-Column Docked Suite | Left: Inputs & Effects; Center: Interactive Canvas; Right: Parameter Inspector & Export (both sidebars collapsible) | ✓ |
| Option B: Floating HUD Over Full-Bleed Canvas | Immersive full-screen canvas with floating draggable control panels | |
| Option C: Single Right-Side Tabbed Inspector | Single consolidated drawer with tabs for Media, Effects, Adjustments, and Export | |

**User's choice:** Option A: Three-Column Docked Suite
**Notes:** Replicates Grainrad / Blender layout with collapsible sidebars and floating viewport controls (`-`, `100%`, `+`, `Reset`).

---

## 4. Media Ingestion & Lifecycle

| Option | Description | Selected |
|--------|-------------|:--------:|
| Option A: Smart Auto-Fit + Starter Samples + Video Transport HUD | Bundled 1-click sample media, video play/pause/loop controls, auto-fit canvas, and GPU resolution safety limits | |
| Option B: Blank-Slate Dropzone | Empty canvas standby state with native uncapped media dimensions | ✓ |
| Option C: Multi-Source Picture-in-Picture | Multi-layer composition allowing multiple inputs on one canvas | |

**User's choice:** Option B: Blank-Slate Dropzone — Empty canvas standby state with native uncapped media dimensions
**Notes:** No bundled asset bloat; clean dropzone accepting images, video, and webcam, rendered at native pixel dimensions.

---

## 5. Shader Architecture & Performance Strategy

| Option | Description | Selected |
|--------|-------------|:--------:|
| Option A: Smart Adaptive Render Loop + Glyph Texture Atlas | 60 FPS for video/webcam/animated effects; sleeps on static images; dynamic texture atlas for crisp ASCII glyphs | |
| Option B: Unconditional Continuous 60 FPS Loop | Always-on animation loop regardless of media type or effect | |
| Option C: Compute Shader Workgroups | WebGPU compute shader architecture with separate WebGL2 fragment fallback | ✓ |

**User's choice:** Option C: Compute Shader Workgroups — WebGPU compute shader architecture with separate WebGL2 fragment fallback
**Notes:** 16x16 workgroup dispatches with shared memory for high-performance transformations, plus WebGL2 fragment fallback.

---

## 6. Effect Graph & ASCII Creative Engine

| Option | Description | Selected |
|--------|-------------|:--------:|
| Option A: Stage-Gated Chain | Pre-Tone Adjustments -> 16 Primary Effects -> Color Modes -> CRT/VHS Post-FX overlay | ✓ |
| Option B: Arbitrary Multi-Layer Stack | Reorderable layer list allowing multiple effects to chain in custom sequences | |
| Option C: Exclusive Single-Effect | Only one effect runs at a time with no post-processing passes | |

**User's choice:** Option A: Stage-Gated Chain — Pre-Tone Adjustments -> 16 Primary Effects -> Color Modes -> CRT/VHS Post-FX overlay
**Notes:** Linear predictable pipeline with core ramps (Standard, Dense, Simple, Blocks) and custom character ramp string support.

---

## 7. Export Capabilities & Acceptance Criteria

| Option | Description | Selected |
|--------|-------------|:--------:|
| Option A: Complete Client Export Suite + Quick Canvas Recorder | High-res PNG, JPEG, Vector SVG, plain .txt, plus in-browser quick WebM/GIF recording | ✓ |
| Option B: Strict Static Client Exports Only | Instant PNG, JPEG, SVG, and plain .txt; all video/GIF deferred to Phase 3 backend | |
| Option C: Text & Raster Image Only | PNG, JPEG, and plain .txt only | |

**User's choice:** Option A: Complete Client Export Suite + Quick Canvas Recorder
**Notes:** In-browser export covering PNG, JPEG, SVG, .txt, and quick WebM/GIF canvas capture via MediaRecorder.

---

## the agent's Discretion

- Zustand store architecture for studio state and parameter bindings.
- Tailwind CSS v4 styling tokens and component structure aligned with approved Stitch MCP prototypes.
- Workgroup buffer packing details in WGSL.

## Deferred Ideas

- Phase 3: FastAPI backend service with FFmpeg video transcoding and audio sync, Render & Cloudflare deployment.
- v2: User persistence and preset community gallery (PERSIST-01, PERSIST-02), Three.js standalone 3D export (PERSIST-03).
