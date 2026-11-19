<!-- generated-by: gsd-doc-writer -->
# Configuration Reference

This document details all configuration options, environment variables, and runtime flags available across the Terminal CLI, Web Studio, and Export API backend.

---

## Environment Variables

### Terminal CLI Runtime (`src/config.py`)

All terminal CLI settings can be configured via environment variables without passing command-line arguments:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RGB_ASCII_NO_ADAPTIVE` | `integer` (`0` or `1`) | `0` | Set to `1` to disable dynamic load shedding (`--no-adaptive` CLI equivalent). Byte-reproducible output. |
| `RGB_ASCII_HALF_BLOCK` | `integer` (`0` or `1`) | `0` | Set to `1` to enable experimental half-block mode (`▀`), doubling vertical color density. |
| `RGB_ASCII_NO_COLOR` | `integer` (`0` or `1`) | `0` | Set to `1` to force monochrome output (grayscale ASCII glyphs without ANSI color escapes). |
| `RGB_ASCII_NO_AUDIO` | `integer` (`0` or `1`) | `0` | Set to `1` to disable audio playback even when FFplay and audio streams exist. |
| `RGB_ASCII_SMOOTHING` | `float` (`0.0`..`1.0`) | `0.0` | Exponential temporal alpha blend factor between successive frames. `0.0` disables smoothing. |
| `RGB_ASCII_FPS` | `integer` | `30` | Target playback frame rate override. Overrides video container stream FPS. |
| `RGB_ASCII_PRESET` | `string` | `default` | Name of predefined ASCII luminance ramp (`default`, `dense`, `simple`, `blocks`). |
| `RGB_ASCII_CHARS` | `string` | `" .:-=+*#%@"` | Custom ASCII character gradient string (lowest luminance first, highest last). Overrides preset. |
| `RGB_ASCII_DEBUG` | `integer` (`0` or `1`) | `0` | Set to `1` to print timing diagnostics, dropped frames, audio status, and drift stats to `stderr`. |

### Export API Backend (`src/api/config.py`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | Optional | `development` | Runtime environment tier (`development`, `production`, `test`). |
| `PORT` | Optional | `8000` | Port for the Uvicorn web server to bind on. Provided automatically by Render. |
| `CORS_ORIGINS` | Optional | `https://rgb-ascii.pages.dev,http://localhost:5173` | Comma-delimited list of allowed CORS origins. |
| `TURNSTILE_SECRET_KEY` | **Required in Prod** | `""` | Cloudflare Turnstile secret key for server-side verification. |
| `TURNSTILE_SITE_KEY` | **Required in Prod** | `""` | Cloudflare Turnstile site key exposed to clients. |
| `TURNSTILE_DISABLED` | Optional | `false` | Set to `true` or `1` to bypass captcha verification (development/testing only). |
| `DATABASE_URL` | Optional | `""` | Optional Postgres connection string (Neon free tier) for job auditing. |

<!-- VERIFY: Turnstile secret and site keys must be provisioned in the Cloudflare Turnstile dashboard. -->

### Web Studio Frontend (`web/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | Optional | `http://localhost:8000` | Base URL pointing to the FastAPI export backend. |
| `VITE_TURNSTILE_SITE_KEY` | Optional | `""` | Cloudflare Turnstile public site key for client challenge verification. |

---

## Configuration Files

### 1. Python Project Configuration (`pyproject.toml`)

Declarative configuration for Python packaging, linters, and test runners:

```toml
[project]
name = "rgb-ascii"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
rgb-ascii = "src.main:main"

[tool.ruff]
target-version = "py310"
line-length = 100
select = ["E4", "E7", "E9", "F"]

[tool.mypy]
python_version = "3.10"
files = ["src"]
strict = false
warn_return_any = true
```

### 2. Render Deployment Specification (`render.yaml`)

Infrastructure-as-code definition for the FastAPI backend microservice:

```yaml
services:
  - type: web
    name: rgb-ascii-api
    runtime: python
    buildCommand: "pip install -r requirements.txt && pip install -e ."
    startCommand: "uvicorn src.api.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: TURNSTILE_SECRET_KEY
        sync: false
      - key: TURNSTILE_SITE_KEY
        sync: false
```

### 3. Cloudflare Pages Configuration (`wrangler.toml`)

Deployment specification for the Vite SPA:

```toml
name = "rgb-ascii"
compatibility_date = "2024-11-01"
pages_build_output_dir = "web/dist"
```

---

## Required vs Optional Settings

### Backend Production Validation
When `ENVIRONMENT=production`, `src/api/config.py` enforces startup validation:
- If `TURNSTILE_DISABLED` is not enabled, both `TURNSTILE_SECRET_KEY` and `TURNSTILE_SITE_KEY` must be populated with non-empty strings. Missing credentials raise a `ValueError` during initialization, preventing unprotected deployment.

### Resource & Safety Limits
Hardened operational defaults protect the backend from memory exhaustion:
- **Max chunk size**: `5 MB` per streamed chunk.
- **Max video duration**: `60.0` seconds maximum transcode window.
- **Max animated GIF duration**: `15.0` seconds.
- **Storage quota**: `500 MB` maximum disk space in `/tmp/rgb_ascii_exports/`.
- **Inactivity timeout**: `60` seconds before orphaned partial uploads are cleaned up.
- **Encoding timeout**: `90` seconds hard subprocess limit per FFmpeg job.
- **Max job lifetime**: `600` seconds (10 minutes) before completed artifacts are deleted.

---

## Character Presets Reference

The terminal renderer and web studio provide 4 pre-calculated character ramps:

| Preset | Glyph Ramp | Primary Use Case |
|--------|------------|------------------|
| `default` | ` .:-=+*#%@` | Balanced contrast for general video playback (10 steps). |
| `dense` | ` .'\`^",:;Il!i><~+_-?][}{1)(\|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$` | Maximum tonal detail on high-resolution displays (70 steps). |
| `simple` | ` .:-=+*#%@` | Coarse, high-legibility glyphs for low-resolution viewports. |
| `blocks` | ` ░▒▓█` | Unicode block characters for distinct graphic/dithered styles. |
