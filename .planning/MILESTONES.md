# Milestones

## v1.0 RGB ASCII & Retro FX Studio (Shipped: 2026-11-18)

**Phases completed:** 3 phases, 12 plans, 17 tasks

**Key accomplishments:**
- Terminal module pruned to git history, 36-symbol public facade exported from `src`, main.py decoupled to a duck-typed headless frame sink, and `status_rows` purged — 379 existing run()-level tests pass unchanged.
- Terminal-only tests pruned to git history, 4 stale TerminalRenderer monkeypatches replaced with headless `_headless_output_size` pins, and the whole engine certified green: 387/387 tests hermetically, mypy zero errors in 11 source files, ruff all-checks-passed.
- Monochrome Grainrad studio design approved by user: DESIGN.md token spec (IBM Plex Mono, three-column creative-suite shell, canvas-content-only color exception), two regenerated Stitch prototype PNGs, and the stitch-prototypes.json identifier registry for later implementation plans.
- React 19 + Vite 8 + Tailwind v4 studio SPA with three-column docked layout, pan/zoom ViewportHUD, and a blank-slate dropzone ingesting images/videos at native dimensions plus live webcam via getUserMedia — styled per the approved 02-01 monochrome Grainrad tokens
- 2026-11-18
- 2026-11-18
- 2026-11-18
- FastAPI microservice core, 8-state export job state machine with process-local concurrency lock, Cloudflare CIDR ingress defense, Turnstile verification, and SlowAPI rate limiting.
- Low-memory FFmpeg video and animated GIF transcoding engine, real-time telemetry streaming via `-progress pipe:1`, server-side audio fallback seeking muxer, and active-PID protected storage janitor.
- Client-side Web Audio graph, DPI decoupling canvas lock, bounded chunk sequencer with upload backpressure, Cloudflare Turnstile widget, and four-stage retro terminal telemetry modal.

---
