# Requirements: RGB ASCII & Retro FX Studio

**Defined:** 2026-11-16
**Core Value:** Instant, real-time retro visual transformations and high-fidelity media export across web and video formats, operating reliably at $0/month on free-tier cloud infrastructure.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Codebase Modernization

- [x] **MODERN-01**: Existing Python codebase is audited, dead terminal-only code (`src/terminal.py`) is safely archived, and core modules (`src/renderer.py`, `src/video.py`, `src/audio.py`, `src/config.py`) are refactored into a reusable core.
- [x] **MODERN-02**: Core math routines and frame transformations pass strict linting (`ruff`) and static type checks (`mypy`) with zero errors.
- [x] **MODERN-03**: Test suite is updated to verify modernized core modules hermetically, ensuring zero regressions in luminance calculations, box-averaging, and FFmpeg error classifications.

### UI/UX Design & Review Gate

- [ ] **STUDIO-01**: Visual studio interface is prototyped and designed iteratively using Stitch MCP, establishing dark/light theme tokens, collapsible inspectors, and parameter controls.
- [ ] **STUDIO-02**: Stitch UI/UX design is presented for user review and explicitly approved by the user before any visual frontend implementation begins.
- [ ] **STUDIO-03**: Interactive canvas viewport supports responsive pan, zoom controls (`-`, `+`, `100%`, `Reset`), and active theme toggling.

### Client-Side Real-Time Shader Pipeline

- [ ] **SHADER-01**: Client-side WebGPU engine renders real-time ASCII transformations with parametric cell scaling, character spacing, and selectable ramps (Standard, Dense, Simple, Blocks).
- [ ] **SHADER-02**: Real-time shaders implement Grainrad-inspired retro effects: Dithering (Floyd-Steinberg & Bayer), Halftone dot screens, and VHS/CRT scanlines.
- [ ] **SHADER-03**: Real-time parametric color/tone adjustments provide sliders for Brightness, Contrast, Saturation, Hue Rotation, Gamma, and Invert.
- [ ] **SHADER-04**: Automatic compatibility fallback from WebGPU to WebGL2 shader pipeline ensures flawless rendering on devices lacking WebGPU support.

### Media Ingestion & Client Export

- [ ] **MEDIA-01**: User can drag and drop or browse local image files (PNG, JPG, WebP, GIF) and video files (MP4, WebM) with automatic aspect-ratio viewport preservation.
- [ ] **MEDIA-02**: User can activate live webcam input via browser `getUserMedia` and view real-time retro shader transformations.
- [ ] **MEDIA-03**: User can instantly export processed canvas outputs client-side as PNG, JPEG, SVG, and plain ASCII text (`.txt`).

### Backend Media Transcoding Service

- [x] **EXPORT-01**: FastAPI backend exposes `/api/export/video` accepting media uploads and serialized shader parameter configurations.
- [x] **EXPORT-02**: Backend decodes video, applies retro transformations via modernized core algorithms, and outputs rendered MP4 video and animated GIF with audio sync via FFmpeg.
- [x] **EXPORT-03**: Backend processes media in bounded streaming chunks using temporary files, staying strictly within Render's 512MB RAM ceiling.
- [x] **EXPORT-04**: Backend exposes `/api/health` allowing client-side background pre-warming to mitigate free-tier container cold starts.

### Git-Driven Deployment & Zero-Cost Infrastructure

- [x] **INFRA-01**: Cloudflare Pages configuration (`wrangler.toml`) defines static build commands, edge routing, and SPA fallback.
- [x] **INFRA-02**: Render Blueprint (`render.yaml`) defines Git-driven deployment for the FastAPI service with FFmpeg on the free tier.
- [x] **INFRA-03**: Neon Serverless PostgreSQL schema and connection scaffolding is documented and ready for future persistence without requiring active instances in v1.
- [x] **INFRA-04**: Production deployment verified to run completely within free-tier limits at $0/month with zero ongoing maintenance costs.

## v2 Requirements

Deferred to future releases. Tracked but not in current roadmap.

### Community & Persistence

- **PERSIST-01**: User accounts and project workspaces saved in cloud database via Neon PostgreSQL.
- **PERSIST-02**: Community preset sharing gallery allowing artists to publish and clone effect recipes.
- **PERSIST-03**: Standalone Three.js 3D embeddable HTML export package.
- **PERSIST-04**: Additional specialized shader packs (Matrix Rain, Voronoi, Wave Lines, Pixel Sort).

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Interactive Terminal CLI Player | Pivoting entirely to Web application; maintaining two separate UI engines creates unnecessary maintenance overhead. |
| Proprietary Grainrad Source Code Duplication | Clean-room open-source functional implementation of retro shaders and workflows. |
| Mandatory User Authentication for v1 | Keeps the application an instantly accessible, frictionless creative playground with zero database cost. |
| Paid Dedicated Cloud GPU Instances | Real-time shaders execute on client GPU; video export runs on free-tier CPU compute. |
| Unbounded Video File Uploads | Free cloud limits (512MB RAM) require enforcing a 60-second video length limit on video exports. |

## Traceability

Which phases cover which requirements. (Will be mapped during roadmap creation).

| Requirement | Phase | Status |
|-------------|-------|--------|
| MODERN-01 | Phase 1 | Complete |
| MODERN-02 | Phase 1 | Complete |
| MODERN-03 | Phase 1 | Complete |
| STUDIO-01 | Phase 2 | Pending |
| STUDIO-02 | Phase 2 | Pending |
| STUDIO-03 | Phase 2 | Pending |
| SHADER-01 | Phase 2 | Pending |
| SHADER-02 | Phase 2 | Pending |
| SHADER-03 | Phase 2 | Pending |
| SHADER-04 | Phase 2 | Pending |
| MEDIA-01 | Phase 2 | Pending |
| MEDIA-02 | Phase 2 | Pending |
| MEDIA-03 | Phase 2 | Pending |
| EXPORT-01 | Phase 3 | Pending |
| EXPORT-02 | Phase 3 | Pending |
| EXPORT-03 | Phase 3 | Pending |
| EXPORT-04 | Phase 3 | Pending |
| INFRA-01 | Phase 3 | Pending |
| INFRA-02 | Phase 3 | Pending |
| INFRA-03 | Phase 3 | Pending |
| INFRA-04 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-11-16*
*Last updated: 2026-11-16 after initialization*
