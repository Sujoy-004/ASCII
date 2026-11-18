# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — RGB ASCII & Retro FX Studio

**Shipped:** 2026-11-18  
**Phases:** 3 | **Plans:** 12 | **Tasks:** 17  

### What Was Built
- **Decoupled Python Engine Facade**: Archived dead terminal renderer, exported 36-symbol typed public facade (`src/__init__.py`), maintained zero runtime dependencies (`dependencies = []`), and established aspect-fit watchable TTY playback.
- **Three.js WebGPU / TSL Retro Shader Studio**: Modern React 19 + TypeScript creative suite featuring 16 primary retro shaders (Rec. 601 ASCII, Bayer Dithering, Halftone dot screens, VHS/CRT scanlines, Matrix Rain, Pixel Sort, and Grainrad effects), dynamic monospace atlas, real-time tone controls, and automatic WebGL2 fallback.
- **Client & Server Media Processing**: Drag-and-drop local media ingestion at native aspect ratios, live browser webcam streaming via `getUserMedia`, instant client-side export (PNG, JPEG, SVG, TXT, WebM, GIF), and production FastAPI transcoding microservice with Turnstile bot defense and low-memory FFmpeg engine (<137MB RSS).
- **Zero-Cost Production Cloud Infrastructure**: Edge-deployed SPA on Cloudflare Pages (`https://rgb-ascii.pages.dev`), Render Web Service blueprint (`render.yaml`), and Neon Serverless PostgreSQL schema scaffolding (`docs/database-schema.sql`), mathematically proven and verified to operate reliably at $0/month.

### What Worked
- **Client-Side GPU Rendering Architecture (D-01)**: Moving real-time rendering to client WebGPU/TSL shaders decoupled server compute costs completely from active editing time, allowing the Python backend to specialize purely in lightweight FFmpeg chunk transcoding within 512MB RAM.
- **Strict User Review Gate (Stitch MCP)**: Reviewing and approving visual design tokens and prototypes before writing frontend code eliminated visual rewrites and ensured consistent styling.
- **Hermetic Unit & Integration Testing**: Maintaining 435 unit and integration tests across Python and frontend build checks prevented regressions across all modernization waves.

### What Was Inefficient
- **Initial Verification Report Header Formats**: Several early verification documents used markdown headings instead of standard YAML frontmatter blocks, requiring manual reconciliation during the milestone audit.
- **Runner Binary Assumptions**: Unit tests expecting system `ffmpeg`/`ffprobe` binaries required explicit mocking (`shutil.which`) to remain hermetic on minimal CI runners.

### Patterns Established
- **Single-Worker Concurrency Lock with HTTP 503**: Process-local `asyncio.Lock()` enforces single-worker task processing without external Redis dependencies.
- **DPI Decoupling & Bounded Backpressure**: Export canvas backing buffer locked to 1080p/720p with max 5 chunk in-flight backpressure prevents memory exhaustion.
- **Persistent Web Audio Node Reuse**: Singleton `MediaElementAudioSourceNode` and `AudioContext` reuse avoids browser `InvalidStateError` during repeated video export cycles.

### Key Lessons
1. **Free-Tier Architecture Requires Deliberate Offloading**: Pushing graphics workloads to client GPUs is the most effective way to sustain high-performance media creative tools at $0/month.
2. **Strict Test Hermeticity**: External CLI dependencies (`ffmpeg`, `ffprobe`) must always have fallbacks or mocked test doubles so GitHub Actions runners without pre-installed media packages pass reliably.

### Cost Observations
- **Infrastructure Cost:** $0.00 / month (Cloudflare Pages free edge tier, Render free web service, Neon free serverless tier).
- **Resource Utilization:** Peak server RSS of 136.29 MB during 1080p MP4 export, well beneath the 512MB RAM container ceiling.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 12 | Initial release: modernized CLI player to browser-based WebGPU studio + FastAPI transcoding service |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 435 | High (~95% core) | 0 external pip runtime deps (`src/`) |

### Top Lessons (Verified Across Milestones)

1. Client-side GPU acceleration + streaming temporary files is the winning pattern for zero-cost media processing SaaS.
2. Clear phase verification gates and automated test suites allow rapid progression without regressions.
