<!-- generated-by: gsd-doc-writer -->
# Development Guide

This guide details local development workflows, code standards, toolchains, and contribution procedures for **RGB ASCII & Retro FX Studio**.

---

## Local Setup

### 1. Repository Setup

```bash
git clone https://github.com/Sujoy-004/ASCII.git
cd ASCII

# Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\Activate.ps1 on Windows

# Install Python development dependencies and editable package
pip install -r requirements.txt
pip install -e .

# Install frontend dependencies
cd web
npm install
cd ..
```

### 2. Environment Configuration

For local development of the backend API, create a local `.env` file or export environment variables:

```bash
export ENVIRONMENT=development
export TURNSTILE_DISABLED=true
export CORS_ORIGINS="http://localhost:5173,http://localhost:4173,https://rgb-ascii.pages.dev"
```

---

## Build & Test Commands

### Python Backend & CLI (`pyproject.toml`)

| Command | Description |
|---------|-------------|
| `pytest tests/ -q` | Run full test suite (435 unit and integration tests). |
| `mypy src` | Run static type checking with strict type definitions (`python_version = 3.10`). |
| `ruff check src tests` | Fast Python linting checking syntax, imports, and style rules (`E4`, `E7`, `E9`, `F`). |
| `python -m src.main <video>` | Execute CLI video renderer directly from source. |
| `python bench.py` | Run terminal ASCII rendering benchmark suite. |
| `python bench_export.py` | Benchmark server-side export pipeline and FFmpeg transcode throughput. |

### Web Studio (`web/package.json`)

| Command | Description |
|---------|-------------|
| `npm run dev` | Launch local Vite dev server with Hot Module Reloading (`http://localhost:5173`). |
| `npm run build` | Perform TypeScript type check (`tsc --noEmit`) and bundle client assets with Vite. |
| `npm run preview` | Serve the production bundle locally (`http://localhost:4173`) to test build output. |
| `npx wrangler pages deploy web/dist` | Deploy production bundle directly to Cloudflare Pages. |

---

## Code Style & Standards

### Python Guidelines

- **Standard Library Zero-Runtime Rule**: The core Python package (`src/renderer.py`, `src/timing.py`, `src/video.py`, etc.) must maintain zero third-party dependencies at runtime (`dependencies = []` in `pyproject.toml`). Third-party packages (FastAPI, Uvicorn, SlowAPI) are isolated exclusively to `src/api/`.
- **Absolute Imports**: Always use absolute package imports:
  ```python
  from src.config import Config
  from src.renderer import RGBAsciiRenderer
  ```
- **Type Annotations**: All functions and methods must have complete type signatures using modern pipe union syntax (`str | None`, `int | float`) enabled by `from __future__ import annotations`.
- **Hot-Loop Efficiency**: Avoid memory allocations or string formatting inside rendering loops. Utilize pre-calculated lookup tables (e.g., `_decimal_str` and `_char_table_cache` in `src/renderer.py`).

### TypeScript & React Guidelines

- **Functional Components & Hooks**: Modern React 19 architecture using strict TypeScript typing.
- **Direct Three.js TSL Shaders**: Custom shader nodes in `web/src/engine/shaders/` must be pure Three.js Shading Language (`three/tsl`) node functions, ensuring cross-compatibility across WebGPU and WebGL2 backends.
- **Zustand State Separation**: Media streams, object URLs, and raw `HTMLVideoElement` instances must remain non-reactive and managed via non-reactive refs or singletons (`registerVideoElement`) to avoid unbounded memory re-renders.

---

## Branch Conventions

- **Default Branch**: `main` (production-ready code).
- **Feature Branches**: Prefix with work category:
  - `feat/feature-name` — New user-facing capabilities or shader modes.
  - `fix/bug-description` — Defect fixes and edge-case patches.
  - `perf/optimization` — Throughput or frame pacing optimizations.
  - `docs/doc-update` — Documentation improvements and guides.

---

## Pull Request Process

1. **Verify Hermetic Tests**: Ensure all 435 tests pass before creating a pull request:
   ```bash
   python -m pytest tests/ -q
   ```
2. **Type Checking & Linting**:
   ```bash
   mypy src
   ruff check src tests
   npm --prefix web run build
   ```
3. **Atomic Commits**: Write clear, descriptive commit messages matching conventional commit conventions (`feat: ...`, `fix: ...`, `docs: ...`).
4. **Clean PR Diff**: Do not modify unrelated formatting or create dead code. Keep PR changes surgical and focused.
