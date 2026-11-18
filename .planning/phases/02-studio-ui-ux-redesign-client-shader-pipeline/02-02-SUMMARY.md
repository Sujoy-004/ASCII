---
phase: 02-studio-ui-ux-redesign-client-shader-pipeline
plan: "02-02"
subsystem: ui
tags: [react, react19, vite, tailwind-v4, zustand, typescript, dropzone, webcam, getUserMedia]

# Dependency graph
requires:
  - phase: 02-01
    provides: approved monochrome Grainrad design tokens (DESIGN.md), studio identifiers, prototype visual targets
provides:
  - Vite 8 + React 19 + TypeScript + Tailwind v4 SPA shell in web/ (STUDIO-03)
  - Three-column docked studio layout with collapsible Left/Right rails (D-03)
  - ViewportHUD with [-]/[100%]/[+]/[Reset] zoom, native dimension display, theme toggle (STUDIO-03)
  - Zustand studio store: media, zoom/pan, tone (incl. hueRotation SHADER-03), ASCII params (incl. charSpacing SHADER-01), theme, sidebar collapse
  - Blank-slate standby dropzone with drag-drop + browse ingestion (D-04, MEDIA-01)
  - Live webcam feed via getUserMedia with full track teardown (MEDIA-02)
  - Native uncapped dimension media rendering (D-04)
affects: [02-03 webgpu shader engine canvas mount, 02-04 tone sliders/export drawer, phase 03 media processing pipeline]

# Actuals (#2632) — same scale as the plan's `estimate` (estimateTokens = chars/4 over the realized diff).
actuals:
  tokens: 11712   # chars/4 over the 14 files the plan changed
  tasks: 3
  commits: 3      # MEASURED: git rev-list --count 2db3199..HEAD (pre-SUMMARY)

# Tech tracking
tech-stack:
  added: [react 19, react-dom 19, zustand, vite 8, tailwindcss v4, @tailwindcss/vite, lucide-react, three, gifenc]
  patterns:
    - "Token-backed Tailwind v4 theme: CSS custom properties on :root registered via @theme inline (bg-base/text-dim/bg-active/bg-raised/border-hairline)"
    - "Non-reactive browser resources (MediaStream, object URLs) live in module scope, disposed explicitly — never in Zustand reactive state (T-02-03/T-02-04)"
    - "Registration seam: registerVideoElement / registerBrowseHandler connect persistent DOM nodes to the store without reactive coupling"

key-files:
  created:
    - web/package.json
    - web/vite.config.ts
    - web/tsconfig.json
    - web/index.html
    - web/src/main.tsx
    - web/src/types/studio.ts
    - web/src/components/layout/LeftRail.tsx
    - web/src/components/layout/CenterStage.tsx
    - web/src/components/layout/RightRail.tsx
    - web/src/components/canvas/ViewportHUD.tsx
    - web/src/components/canvas/Dropzone.tsx
  modified:
    - web/src/App.tsx
    - web/src/index.css
    - web/src/store/useStudioStore.ts

key-decisions:
  - "MediaStream and object URLs are kept out of reactive Zustand state — module-level disposal guards (T-02-03/T-02-04) prevent leaks and stale renders"
  - "Dropzone keeps its hidden file input mounted in BOTH standby and active states and registers it as the shared browse handler, so LeftRail source buttons always reach the same ingestion path"
  - "Media renders at native uncapped size via max-w-none + explicit width/height, overriding Tailwind preflight downscaling — the zoom HUD exists to navigate large media"
  - "Webcam <video> element is conditionally rendered per mediaType and registered on mount; unmount stops all tracks so the camera indicator never stays lit"

patterns-established:
  - "Grainrad token discipline: components use token utilities only (bg-base, text-default, text-dim, text-highlight, bg-active, bg-raised, border-hairline); no raw hex in TSX"
  - "Scanline CRT texture is standby-state-only (DESIGN.md §114)"
  - "Every interaction is a square-corner, hairline-bordered, 24px-row mono control; duration-fast transitions"

requirements-completed: [STUDIO-03, MEDIA-01, MEDIA-02]

# Coverage metadata (#1602) — drives deterministic UAT routing in verify-work.
coverage:
  - id: D1
    description: Vite + React 19 + TypeScript + Tailwind v4 SPA shell in web/ builds with zero errors (STUDIO-03)
    requirement: STUDIO-03
    verification:
      - kind: other
        ref: "command: npm --prefix web run build (tsc --noEmit && vite build)"
        status: pass
    human_judgment: false
  - id: D2
    description: Three-column docked creative suite layout renders responsively with collapsible Left/Right rails (D-03)
    requirement: STUDIO-03
    verification:
      - kind: other
        ref: "command: npm --prefix web run build (component existence + type-correctness only)"
        status: pass
    human_judgment: true
    rationale: "Layout quality is visual — requires human inspection of the rendered workspace against prototypes/02-01-studio-*.png; no automated UI test asserts column docking or collapse behavior"
  - id: D3
    description: ViewportHUD [-]/[100%]/[+]/[Reset] controls update zoom/pan in useStudioStore; theme toggle switches data-theme (STUDIO-03)
    requirement: STUDIO-03
    verification:
      - kind: other
        ref: "command: npm --prefix web run build (wiring type-checks; runtime interaction unasserted)"
        status: pass
    human_judgment: true
    rationale: "Interactive HUD behavior needs a human clicking controls in the running dev server; no test harness asserts store updates from clicks"
  - id: D4
    description: Blank-slate dropzone appears on clean load and accepts drag-drop/browse of PNG, JPG, WebP, GIF, MP4, WebM at native uncapped dimensions (D-04, MEDIA-01)
    requirement: MEDIA-01
    verification:
      - kind: other
        ref: "command: npm --prefix web run build (accept attr + drop handlers type-check; runtime drag-drop unasserted)"
        status: pass
    human_judgment: true
    rationale: "Drag-and-drop and dimension display require a human dropping real files in the browser; browser file/drag APIs have no automated test coverage in this scaffold"
  - id: D5
    description: Live webcam feed via getUserMedia with clean track teardown on stop/unmount (MEDIA-02)
    requirement: MEDIA-02
    verification:
      - kind: other
        ref: "command: npm --prefix web run build (getUserMedia call + teardown paths type-check; runtime camera flow unasserted)"
        status: pass
    human_judgment: true
    rationale: "Camera permission prompt, live feed and the browser camera-indicator turning off on stop can only be verified by a human on real hardware"

# Metrics
duration: 15 min (continuation session; Tasks 1-2 from prior interrupted session)
completed: 2026-11-18
status: complete
---

# Phase 02 Plan 02: Studio SPA Shell + Media Ingestion Summary

**React 19 + Vite 8 + Tailwind v4 studio SPA with three-column docked layout, pan/zoom ViewportHUD, and a blank-slate dropzone ingesting images/videos at native dimensions plus live webcam via getUserMedia — styled per the approved 02-01 monochrome Grainrad tokens**

## Performance

- **Duration:** 15 min (this continuation session; completed Tasks 1-2 in the prior session before a network outage mid-Task-3)
- **Completed:** 2026-11-18
- **Tasks:** 3/3
- **Files modified:** 14 (11 created, 3 modified)

## Accomplishments
- Full SPA shell in `web/`: Vite 8, React 19, TypeScript strict, Tailwind v4 with the 02-01 DESIGN.md token set, Zustand store, Lucide icons — zero build errors (STUDIO-03)
- Three-column docked creative suite: LeftRail (media source, 16 effect tiles, preset chips), CenterStage (pan/zoom canvas), RightRail (inspector/tone/export containers), both rails collapsible to icon docks (D-03)
- ViewportHUD: [-] [100%] [+] [Reset], native dimension tag, dark/light theme toggle (STUDIO-03)
- Blank-slate dropzone per D-04: dashed hairline frame, `+` affordance, scanline standby texture, stage-wide drag-drop with overlay tint and solid-frame step
- Media ingestion: `loadMediaFile` with MIME dispatch, previous-URL revocation (T-02-03), natural image/video dimension extraction, viewport reset on load (MEDIA-01)
- Webcam: `startWebcam`/`stopWebcam` with full `MediaStreamTrack.stop()` teardown, element detach, and unmount cleanup so the camera indicator never stays lit (MEDIA-02, T-02-04)

## Task Commits

1. **Task 1: SPA shell bootstrap (tracer)** - `952fffa` (feat)
2. **Task 2: three-column layout + ViewportHUD** - `daf8f54` (feat)
3. **Task 3: dropzone + media/webcam ingestion** - `b964dff` (feat)

**Plan metadata:** `33932b6` (docs: summary - SPA scaffold complete, incl. Self-Check: PASSED)

_Note: Tasks 1-2 were committed by the prior executor session before the network outage; this session resumed mid-Task-3._

## Files Created/Modified
- `web/package.json` - SPA deps (react 19, zustand, three, gifenc, lucide-react, vite 8, tailwind v4)
- `web/vite.config.ts` - @tailwindcss/vite + @vitejs/plugin-react, no PostCSS boilerplate
- `web/tsconfig.json` - strict mode, DOM types, ESNext resolution
- `web/index.html` - viewport meta, dark background
- `web/src/index.css` - Tailwind v4 import + Grainrad token registration (@theme inline)
- `web/src/main.tsx` - React 19 mount
- `web/src/App.tsx` - docked studio shell (24px titlebar, 3 columns, 24px statusbar), theme on document root
- `web/src/types/studio.ts` - MediaType, EffectMode, ToneSettings (hueRotation SHADER-03), AsciiSettings (charSpacing SHADER-01), Dimensions, ExportConfig
- `web/src/store/useStudioStore.ts` - Zustand store + module-level MediaStream/object-URL disposal + loadMediaFile/startWebcam/stopWebcam/clearMedia/openFileBrowser
- `web/src/components/layout/LeftRail.tsx` - media source switcher (wired to browse/webcam), 16 effect grid, preset chips, collapse
- `web/src/components/layout/CenterStage.tsx` - pan/zoom transform layer, native-dimension media rendering, stage-wide drag-drop, webcam video registration
- `web/src/components/layout/RightRail.tsx` - inspector/tone/export containers, collapse
- `web/src/components/canvas/ViewportHUD.tsx` - floating zoom/percent/reset/dimensions/theme HUD
- `web/src/components/canvas/Dropzone.tsx` - standby card + shared hidden file input

## Decisions Made
- MediaStream and object URLs live in module scope (never in reactive state); explicit disposal functions guard against leaks (T-02-03/T-02-04)
- Single hidden file input in Dropzone doubles as the shared browse handler for LeftRail source buttons — one ingestion path through `loadMediaFile`
- Media renders at native uncapped size (`max-w-none` overrides Tailwind preflight); the zoom HUD is the navigation tool for oversized media
- Webcam video element registers on mount via `registerVideoElement`; effect cleanup stops tracks on unmount (T-02-04)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed predecessor's uncommitted WIP compile error in the store**
- **Found during:** Task 3 (continuation after network outage)
- **Issue:** `stopWebcamInternal(get)` referenced `set`, which was not in scope — the file could not compile (Task 3 was interrupted mid-write)
- **Fix:** Changed signature to `stopWebcamInternal(set, get)` and updated all three call sites
- **Files modified:** web/src/store/useStudioStore.ts
- **Verification:** `npm --prefix web run build` exits 0
- **Committed in:** b964dff

**2. [Rule 2 - Missing Critical] Unmount-time track teardown for the webcam**
- **Found during:** Task 3
- **Issue:** T-02-04 mitigation requires stopping all MediaStreamTracks when the component unmounts; the WIP only stopped tracks on explicit stop
- **Fix:** CenterStage registration effect cleanup calls `stopWebcam()` on unmount (no-op in all other paths — stream already null)
- **Files modified:** web/src/components/layout/CenterStage.tsx
- **Verification:** build passes; teardown path is a no-op unless a live stream exists at unmount
- **Committed in:** b964dff

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes were required for the task to compile and satisfy T-02-04. No scope creep.

## Issues Encountered
- The prior executor session died from a network outage mid-Task-3, leaving the store file modified and uncompilable. Resolved by reading the WIP, completing its intent, and fixing the compile error — no re-work of Tasks 1-2 was needed.

## Known Stubs
None preventing the plan goal. Note: the standby `<canvas>` in CenterStage is an intentional mount point for the plan 02-03 WebGPU/WebGL engine, and the RightRail inspector/tone/export sections are containers per the plan (parameter controls arrive with the shader engine phase).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `web/` SPA builds cleanly; store exposes media URL/type/dimensions plus tone/ASCII settings ready for the 02-03 WebGPU shader engine to consume
- CenterStage's standby canvas placeholder marks the engine mount; `registerVideoElement` provides the stream feed seam
- No blockers

---
*Phase: 02-studio-ui-ux-redesign-client-shader-pipeline*
*Completed: 2026-11-18*

## Self-Check: PASSED

All 13 created/modified key files exist on disk; all 4 plan commits (952fffa, daf8f54, b964dff, e05e4e4) are ancestors of HEAD; working tree clean; `npm --prefix web run build` passes (tsc --noEmit + vite build, zero errors).
