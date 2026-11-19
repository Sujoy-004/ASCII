<!-- generated-by: gsd-doc-writer -->
# Deployment Guide

This document describes deployment architecture, build pipelines, production configuration, and rollback procedures for **RGB ASCII & Retro FX Studio**.

---

## Deployment Targets

The platform is architected for strict $0/month operations across free-tier serverless and container infrastructure:

| Component | Target Platform | Specification File | Live URL |
|-----------|-----------------|--------------------|----------|
| **Frontend Studio & Landing Page** | Cloudflare Pages | `wrangler.toml` | `https://rgb-ascii.pages.dev` (Overview), `https://rgb-ascii.pages.dev/studio/` (Studio) |
| **Backend Export API** | Render (Free Web Service) | `render.yaml` | <!-- VERIFY: Deployed Render backend service URL --> `https://rgb-ascii-api.onrender.com` |

---

## Build Pipeline & Deployment Workflows

### 1. Web Studio Deployment (Cloudflare Pages)

The frontend is an optimized SPA built with Vite and deployed directly to Cloudflare's global edge network.

#### Production Build Command
```bash
cd web
npm run build
```
This produces optimized production assets in `web/dist/`, including `index.html`, minified JS/CSS bundles, and `_redirects` for client-side routing.

#### Deploy with Wrangler
```bash
npx wrangler pages deploy web/dist --project-name=rgb-ascii --commit-dirty=true
```

Upon successful deployment, Cloudflare immediately propagates DNS and serves the product landing page under `https://rgb-ascii.pages.dev/` and the interactive studio under `https://rgb-ascii.pages.dev/studio/` with edge SSL and HTTP/3 support. Non-matching paths return a custom 404 page with 404 status.

---

### 2. Export API Backend Deployment (Render)

The backend microservice runs as an auto-managed Python container on Render using declarative Infrastructure-as-Code (`render.yaml`):

```yaml
services:
  - type: web
    name: rgb-ascii-api
    runtime: python
    region: oregon
    plan: free
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

#### Build Pipeline Execution
1. **Container Initialization**: Render clones the repository on `git push origin main`.
2. **Dependency Installation**: Executes `pip install -r requirements.txt && pip install -e .` to install standard backend packages and link the local package.
3. **Daemon Startup**: Launches Uvicorn on `$PORT` assigned dynamically by the host.
4. **Health Check Probe**: Probes `/health` endpoint before redirecting public HTTP traffic.

---

## Production Environment Setup

Configure the following environment variables in the deployment dashboards:

### Cloudflare Pages Dashboard
- `VITE_API_BASE_URL`: Full HTTPS URL of the deployed Render backend (e.g., `https://rgb-ascii-api.onrender.com`).
- `VITE_TURNSTILE_SITE_KEY`: Public site key generated from Cloudflare Turnstile dashboard.

### Render Service Dashboard
- `ENVIRONMENT`: Set to `production`.
- `TURNSTILE_SECRET_KEY`: Private secret key for validating Turnstile captcha tokens.
- `TURNSTILE_SITE_KEY`: Public site key matching the frontend configuration.
- `CORS_ORIGINS`: `https://rgb-ascii.pages.dev`.

<!-- VERIFY: Turnstile secret and site keys in Cloudflare Zero Trust dashboard. -->

---

## Rollback Procedures

### Frontend (Cloudflare Pages)
1. **Instant Dashboard Rollback**:
   - Navigate to **Cloudflare Dashboard** → **Workers & Pages** → **rgb-ascii** → **Deployments**.
   - Select any previous stable deployment and click **Rollback to this deployment**.
2. **CLI Rollback**:
   - List recent deployment IDs:
     ```bash
     npx wrangler pages deployment list --project-name=rgb-ascii
     ```
   - Rollback / promote a previous deployment ID:
     <!-- VERIFY: Exact wrangler rollback syntax per active wrangler CLI version. -->
     ```bash
     npx wrangler pages deployment switch <deployment-id> --project-name=rgb-ascii
     ```

### Backend (Render)
1. Navigate to **Render Dashboard** → **rgb-ascii-api** → **Events**.
2. Locate the last known good deployment commit.
3. Click **Rollback** on the deployment card to instantly redeploy that artifact.

---

## Monitoring & Health Checks

- **Health Ping**: The `/health` endpoint responds with `{ "status": "ok", "version": "1.0.0" }`. Ping periodically to pre-warm the free-tier Render container and prevent cold-start latency:
  ```bash
  curl -I https://rgb-ascii-api.onrender.com/health
  ```
- **Live Logs**:
  - Cloudflare Pages: Real-time request telemetry available in the Cloudflare Pages deployment dashboard.
  - Render API: Access structured runtime logs in the Render service console for transcode durations and SlowAPI rate limit events.
