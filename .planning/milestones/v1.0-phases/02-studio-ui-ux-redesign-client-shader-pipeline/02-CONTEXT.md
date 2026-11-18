# Phase 2: Studio UI/UX Redesign & Client Shader Pipeline - Context

**Gathered:** 2026-11-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Prototype the studio interface via Stitch MCP, obtain explicit user approval on visual designs, and build the React + TypeScript SPA featuring a Three.js WebGPU compute shader engine (with WebGL2 fallback), 1:1 Grainrad 16-shader parity, blank-slate media/webcam ingestion, three-column docked studio ergonomics, and instant client-side exports (PNG, JPEG, SVG, TXT, WebM/GIF).

</domain>

<decisions>
## Implementation Decisions

### 1. Engine Foundation & Grainrad Architecture Alignment
- **D-01:** Three.js WebGPU / TSL Foundation (Grainrad Mirror). Build on Three.js's modern WebGPU engine with automatic WebGL fallback, clean WGSL/TSL compute passes, and native texture atlas handling matching Grainrad's production architecture. — **Reversibility:** costly — Shifting rendering engines later touches all shader bindings, uniform bindings, and viewport canvas lifecycle.

### 2. Product Scope & Parity Boundary
- **D-02:** Full 16-Shader Grainrad Parity in v1. Implement all 16 Grainrad shaders in v1: ASCII, Dithering (Bayer & Floyd-Steinberg), Halftone (Dot grid), Matrix Rain, Dots, Contour, Pixel Sort, Blockify, Threshold, Edge Detection, Crosshatch, Wave Lines, Noise Field, Voronoi, VHS/CRT Scanlines, plus global Tone Adjustments. — **Reversibility:** reversible — Adding or toggling individual shader modules is decoupled.

### 3. Studio Workspace & Interaction Design
- **D-03:** Three-Column Docked Creative Suite. Replicate Grainrad/Blender studio ergonomics: Left Rail (Media Input, 16 Effect Selectors, Presets), Center Stage (Interactive Canvas with pan/zoom HUD controls `[-] [100%] [+] [Reset]` and dropzone overlay), and Right Rail (Parameter Inspector, Global Tone Adjustments, Export drawer). Both sidebars collapse to slim icon rails for distraction-free canvas focus. — **Reversibility:** costly — Shapes layout grid, responsive CSS, and inspector state wiring.

### 4. Media Ingestion & Lifecycle
- **D-04:** Blank-Slate Standby Dropzone with Native Uncapped Dimensions. Clean, minimalist standby dropzone ("Drop file or click to browse", supporting PNG, JPG, WebP, GIF, MP4, WebM, and live webcam via `getUserMedia`). Media renders at native uncapped dimensions with 1:1 pixel fidelity without forced downscaling or bundled demo asset clutter. — **Reversibility:** reversible — Adding preloaded sample assets or resolution clamps later is trivial.

### 5. Shader Architecture & Performance Strategy
- **D-05:** Compute Shader Workgroups with WebGL2 Fallback. Dispatch WebGPU compute shaders in 16x16 workgroups with shared workgroup memory for heavy pixel operations (dithering, sorting, convolution, and ASCII mapping), paired with a dedicated WebGL2 fragment shader pipeline for fallback compatibility. — **Reversibility:** costly — Compute pipeline dispatch logic and memory layouts differ from standard fragment shaders.

### 6. Effect Graph & ASCII Creative Engine
- **D-06:** Stage-Gated Linear Processing Chain. Fixed sequential pipeline: `Source Media` → `Pre-Tone Adjustments` (Brightness, Contrast, Saturation, Gamma) → `Primary Effect` (1 of 16 Grainrad shaders) → `Color Grading` (Original TrueColor, Monochrome Phosphor/Amber, Duotone) → `Post-FX Overlay` (CRT/VHS scanlines & curvature).
- **D-07:** Parameterized ASCII Engine with Custom Ramp Support. Support 4 core ramps (`Standard`, `Dense`, `Simple`, `Blocks`) matching `src/config.py` plus freeform custom character string input; cell scaling, character spacing, and inverted luminance ramps. — **Reversibility:** reversible — Pipeline stages and ramp formulas can be extended without breaking architecture.

### 7. Export Capabilities & Acceptance Criteria
- **D-08:** Complete Client Export Suite + Quick Canvas Recorder. In-browser instant downloads: High-res PNG, JPEG, scalable vector SVG (with color glyph spans), raw `.txt` ASCII character grid; plus in-browser quick WebM/GIF canvas recording via `MediaRecorder` for rapid social sharing. Heavy 60s video transcoding hooks into Phase 3 backend.
- **D-09:** Mandatory Stitch MCP UI Approval Gate. Visual studio interface and design system must be prototyped with Stitch MCP and explicitly approved by the user before writing frontend React/Vite code. — **Reversibility:** one-way — Core workflow governance and quality control checkpoint.

### the agent's Discretion
- State management implementation (Zustand store architecture for tool settings, media state, and UI toggles).
- Exact WGSL compute workgroup layout optimizations and buffer packing.
- UI styling implementation details using Tailwind CSS v4 / modern styling tokens matching Stitch MCP prototypes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Specifications & Governance
- `.planning/PROJECT.md` — Core value, constraints, and architecture decisions
- `.planning/ROADMAP.md` — Phase 2 scope and success criteria (STUDIO-01..03, SHADER-01..04, MEDIA-01..03)
- `.planning/REQUIREMENTS.md` — Complete requirements catalog
- `.planning/phases/01-codebase-modernization-core-engine-extraction/01-CONTEXT.md` — Phase 1 decisions (no-Docker, zero-heavy-infra, character ramp definitions)

### Core Engine Algorithms
- `src/renderer.py` — Luminance mapping weights (Rec. 601: `0.299*R + 0.587*G + 0.114*B`) and character lookup logic to mirror in shaders
- `src/config.py` — ASCII ramp definitions (`DEFAULT_CHARS`, `CHAR_PRESETS`)

### External References
- `https://grainrad.com` — Production reference application for UI layout, 16 effect modes, parameter controls, and WebGPU pipeline

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/renderer.py`: Rec. 601 luminance coefficients (`0.299, 0.587, 0.114`) and character ramp presets (`default`, `dense`, `simple`, `blocks`) to maintain 100% mathematical consistency between client shaders and backend transcoding.
- `src/config.py`: Presets dictionary.

### Established Patterns
- Zero-heavy-infra / No-Docker rule (D-02): SPA client builds with standard Node/Vite tooling for static deployment to Cloudflare Pages.
- Hermetic verification and strict typing.

### Integration Points
- Frontend SPA directory: Will be housed cleanly in project root (e.g. `web/` or root Vite setup).
- Phase 3 backend: Export dialog will route heavy 60s video/GIF export parameters to `/api/export/video`.

</code_context>

<specifics>
## Specific Ideas

- **Grainrad 1:1 Parity:** Extracted direct live intelligence from `grainrad.com`. Exact 16 shaders, three-column layout, and parameter controls mirrored in our design system.
- **Compute Shader Performance:** 16x16 workgroup compute shaders with shared memory for heavy transforms, maintaining WebGL2 fragment fallback.
- **Client Autonomy:** Users can record quick WebM/GIF clips directly from canvas in-browser without waiting for backend cold starts.

</specifics>

<deferred>
## Deferred Ideas

- **Phase 3:** FastAPI backend service with FFmpeg chunked video export, `/api/health` pre-warming, Cloudflare Pages + Render Git-driven deployment, and Neon DB scaffolding.
- **v2 (Future Release):** User accounts and cloud preset gallery (PERSIST-01, PERSIST-02), standalone Three.js 3D embeddable HTML export (PERSIST-03).

</deferred>

---

*Phase: 2-Studio UI/UX Redesign & Client Shader Pipeline*
*Context gathered: 2026-11-17*
