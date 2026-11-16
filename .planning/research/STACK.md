# Stack Research

**Domain:** Browser-Based GPU Visual Effects & ASCII Studio with Python Media Transcoding Backend
**Researched:** 2026-11-16
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Vite + React | ^5.4 / ^18.3 | Frontend SPA Framework | Ultra-fast HMR, lightweight bundle size, clean reactive state management for real-time slider controls |
| TypeScript | ^5.6 | Client & API Type Safety | Eliminates runtime interface drift between UI controls, shader uniforms, and export endpoints |
| WebGPU API + WebGL2 Fallback | Modern Standard | Real-Time GPU Shaders | Hardware-accelerated 60fps retro transformations (ASCII, dithering, halftone, VHS) running entirely on client GPU with zero cloud compute cost |
| Tailwind CSS | ^3.4 or ^4.0 | Studio Interface Styling | Rapid, consistent styling for dark-mode studio panels, collapsible drawers, and responsive toolbars |
| FastAPI + Uvicorn | ^0.115 / ^0.32 | Python Backend API | High-throughput async web server, native Pydantic validation, seamless integration with existing Python codebase |
| FFmpeg | ^6.0+ | Server-Side Media Transcoding | Battle-tested industry standard for decoding, scaling, audio extraction, and encoding high-quality MP4/GIF exports |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Zustand | ^4.5 | Client State Management | Managing effect parameters, active presets, zoom state, and export queues without React re-render lag |
| Lucide React | ^0.450 | UI Iconography | Crisp, lightweight icons for toolbar tools, settings sliders, and export format buttons |
| Pydantic | ^2.9 | Request/Response Validation | Validating export jobs, effect options, and video metadata contracts in FastAPI |
| python-multipart | ^0.0.12 | Streaming File Uploads | Handling chunked file uploads (video and image) to FastAPI without memory blowup |
| Neon Serverless Driver / asyncpg | ^0.29 | Relational Persistence (Future) | Serverless PostgreSQL connection over WebSockets or pooling, ready when user persistence is enabled |

### Development & Deployment Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Cloudflare Wrangler | Edge Deployment (`wrangler.toml`) | Deploys static SPA to Cloudflare Pages for unlimited bandwidth and zero hosting costs |
| Render Blueprint | Backend PaaS (`render.yaml`) | Git-driven infrastructure definition for Render free-tier web service running FastAPI and FFmpeg |
| Ruff & Mypy | Python Quality & Typing | Enforces strict syntax, linting, and typing on the modernized Python backend |
| Pytest | Python Automated Testing | Verifies backend endpoints, FFmpeg transcoding workflows, and error handling |

## Installation

```bash
# Frontend setup (in web/ or frontend/)
npm install react react-dom zustand lucide-react
npm install -D vite @vitejs/plugin-react typescript @types/react @types/react-dom tailwindcss postcss autoprefixer

# Backend setup (Python)
pip install fastapi uvicorn[standard] python-multipart pydantic pytest mypy ruff
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| WebGPU + WebGL2 Fallback | Pure Canvas 2D CPU Math | Only for tiny thumbnails; Canvas 2D CPU math cannot maintain 60 FPS video or high-res images |
| React + Vite SPA | Next.js / Nuxt SSR | When public SEO indexing of dynamic routes is paramount; for a client-side creative studio tool, SPA on Cloudflare Pages is faster, simpler, and completely free |
| Render Free Web Service | AWS Lambda / Cloud Run | When budget allows pay-per-use or cold-starts are managed; Render free tier requires $0/month maintenance with zero card charges |
| Client-Side Shader Preview | Server-Side WebRTC Streaming | When target devices are severely constrained thin clients without GPU; server WebRTC introduces high cloud server costs |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Heavy Electron wrapper | Bulky 150MB+ download, complex cross-platform distribution | Browser WebGPU SPA running instantly via URL |
| Synchronous in-memory video encoding | Free-tier RAM limits (512MB on Render) will cause OOM crashes on 1080p video | Chunked disk-backed FFmpeg streaming via temporary files |
| Blocking time.sleep / relative FPS chaining | Accumulates frame drift and desynchronizes video from audio | Monotonic deadline scheduling and WebGL/WebGPU render loops |
| Server-side rendering of preview frames | Consumes server CPU on every slider drag, exhausting free tier instantly | Client-side shader preview; server only renders final export |

## Stack Patterns by Variant

**If Client Browser Supports WebGPU:**
- Execute WGSL (WebGPU Shading Language) compute and fragment shaders directly on GPU.
- Delivers maximum throughput (60+ FPS on 4K images and 1080p video).

**If Client Browser Lacks WebGPU (Older Safari, Firefox without flags):**
- Automatically fall back to WebGL2 GLSL fragment shaders or optimized Canvas 2D fallback.
- Ensures universal access across mobile devices and older desktops.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| FastAPI ^0.115 | Pydantic ^2.9 | Uses Pydantic v2 Core for ultra-fast JSON serialization |
| Vite ^5.4 | React ^18.3 / ^19 | Fully compatible with modern JSX transforms and Tailwind CSS |
| FFmpeg 5.x / 6.x / 7.x | Python 3.10 - 3.13 | Native subprocess streaming using `-fps_mode passthrough` and standard rawvideo |

## Sources

- Official WebGPU Specification & Chrome GPU documentation.
- Cloudflare Pages Documentation (`wrangler.toml` configuration & asset routing).
- Render Blueprint Specification (`render.yaml` services and Docker/native runtimes).
- Grainrad feature and architecture inspection via browser automation.

---
*Stack research for: Browser-Based GPU Visual Effects & ASCII Studio*
*Researched: 2026-11-16*
