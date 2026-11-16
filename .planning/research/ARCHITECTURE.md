# Architecture Research

**Domain:** Hybrid Client-Side WebGPU Studio & Edge-Deployed Python Media Service
**Researched:** 2026-11-16
**Confidence:** HIGH

## Standard Architecture

### System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Tier 1: Client Browser (Edge Delivery)                │
│                           Hosted on Cloudflare Pages                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │   Stitch Studio UI      │  │        Zustand Parameter Store           │  │
│  │   (React / TypeScript)  │  │  (Effect settings, color values, zoom)   │  │
│  └────────────┬────────────┘  └────────────────────┬─────────────────────┘  │
│               │                                    │                        │
│               ▼                                    ▼                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     WebGPU / Canvas FX Engine                         │  │
│  │  - Source Texture Loader (Image, HTML5 Video, MediaStream Webcam)    │  │
│  │  - Fragment Shaders (ASCII, Dither, Halftone, VHS, Adjustments)      │  │
│  │  - 60 FPS Render Loop & Viewport Zoom/Pan Controller                 │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │
                         Export Jobs & │ Heavy Video Rendering
                         API Requests  │ (via HTTPS / fetch)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Tier 2: Backend Media Engine (Render)                   │
│                          FastAPI Web Service ($0 Tier)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │    FastAPI Endpoints    │  │        Streaming Upload / Buffer         │  │
│  │    `/api/export/video`  │  │        (Disk-backed temp files)          │  │
│  │    `/api/health`        │  │                                          │  │
│  └────────────┬────────────┘  └────────────────────┬─────────────────────┘  │
│               │                                    │                        │
│               ▼                                    ▼                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                   Modernized Core Python Engine                       │  │
│  │  - FFmpeg Subprocess Frame Decoder (from `src/video.py`)              │  │
│  │  - Vectorized RGB24 Luminance & ASCII Mapper (`src/renderer.py`)      │  │
│  │  - FFmpeg Transcoding Pipeline & Audio Muxer (`src/audio.py`)         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ Optional (Future)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Tier 3: Database (Neon Serverless PostgreSQL)            │
│                       Stateless in v1 / Scaffolding Ready                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Studio UI (Frontend)** | Input selection, parameter sliders, mode toggles, interactive viewport | React + Vite + Tailwind CSS |
| **Shader Engine (Frontend)** | Zero-latency 60 FPS visual rendering of retro effects onto HTML5 Canvas | WebGPU (WGSL) with WebGL2 fallback |
| **Media Loader (Frontend)** | Ingestion and texture binding for static images, videos, and webcam | HTML5 `<video>`, `ImageBitmap`, `MediaDevices` |
| **API Router (Backend)** | Validates job payloads, queues export tasks, streams results | FastAPI (`APIRouter`, Pydantic models) |
| **Transcoding Service (Backend)** | Reads uploaded media, applies parameters via FFmpeg, encodes MP4/GIF | Subprocess piping to FFmpeg binary |
| **Deployment Manifests** | Infrastructure-as-code for zero-maintenance CI/CD | `wrangler.toml` (Cloudflare) and `render.yaml` (Render) |

## Recommended Project Structure

To maintain a clean boundary between the web client and the backend service while keeping the project cohesive, a clean monorepo layout is recommended:

```
ASCII/
├── .github/
│   └── workflows/
│       └── ci.yml               # CI test & build matrix
├── .planning/                   # GSD planning, research, and requirements
├── client/                      # Frontend SPA (Cloudflare Pages)
│   ├── public/                  # Static assets & favicons
│   ├── src/
│   │   ├── components/          # Studio UI (Inspector, Toolbar, Viewport, Modal)
│   │   ├── shaders/             # WebGPU WGSL & WebGL GLSL shader sources
│   │   │   ├── ascii.wgsl
│   │   │   ├── dither.wgsl
│   │   │   ├── halftone.wgsl
│   │   │   └── vhs.wgsl
│   │   ├── store/               # Zustand state store (effectParams, mediaSource)
│   │   ├── utils/               # Canvas export helpers, WebGPU detection
│   │   ├── App.tsx              # Main studio application
│   │   └── main.tsx             # React DOM entry
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
├── server/                      # Modernized Python Backend (Render Web Service)
│   ├── src/                     # Modernized core modules
│   │   ├── __init__.py
│   │   ├── api/                 # FastAPI routes (`/api/export`, `/api/health`)
│   │   ├── core/                # Core algorithms (`renderer.py`, `video.py`, `audio.py`)
│   │   └── schemas/             # Pydantic request & response contracts
│   ├── tests/                   # Backend pytest suite
│   ├── pyproject.toml           # Server dependencies & tool configs
│   ├── requirements.txt         # Server deployment dependencies
│   └── main.py                  # Uvicorn / FastAPI entry point
├── render.yaml                  # Git-driven Render Blueprint definition
├── wrangler.toml                # Cloudflare Pages / Workers configuration
└── README.md                    # Project documentation
```

### Structure Rationale

- **`client/` separation:** The frontend is decoupled from Python tooling, allowing standard Node/Vite build pipelines and fast Cloudflare Pages deployment.
- **`server/` modernization:** The existing Python codebase is audited, stripped of terminal-only artifacts (`terminal.py`), and organized into clean `core/` and `api/` layers.
- **`render.yaml` & `wrangler.toml` at root:** Enables Git-driven infrastructure where commits to `main` trigger automated deployments on both Cloudflare and Render without manual console steps.

## Architectural Patterns

### Pattern 1: Hybrid Client-Preview / Server-Export
- **What:** Real-time visual parameters (scale, character sets, contrast, dither threshold) are evaluated at 60 FPS in the client's GPU via WebGPU shaders. When the user requests a high-resolution video export, the client sends the source video (or video ID) along with serialized effect parameters to FastAPI, which renders the output via FFmpeg.
- **Why:** Saves 100% of server CPU during normal interactive editing; respects Render free-tier CPU and RAM constraints while giving users instantaneous feedback.

### Pattern 2: Dual WebGPU / WebGL2 Render Pipeline
- **What:** The canvas engine checks `navigator.gpu`. If present and initialized, WGSL shaders run; if unavailable or initialization fails, the engine seamlessly boots a WebGL2 fragment shader pipeline using identical uniform inputs.
- **Why:** Guarantees universal browser compatibility across desktops, tablets, and mobile devices without sacrificing cutting-edge WebGPU performance.

---
*Architecture research for: Hybrid Client-Side WebGPU Studio & Edge-Deployed Python Media Service*
*Researched: 2026-11-16*
