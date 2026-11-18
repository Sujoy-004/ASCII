---
id: 20261118-modernize-web-guidance
type: quick
title: Modernize Web Platform Patterns via Google Chrome Modern Web Guidance
created: 2026-11-18
completed: 2026-11-18
status: complete
files_modified:
  - web/src/export/serverExport.ts
  - web/src/services/exportApi.ts
  - web/src/components/modals/ServerExportModal.tsx
  - web/src/components/panels/ExportDrawer.tsx
---

# Quick Task Summary: Modernize Web Platform Patterns via Google Chrome Modern Web Guidance

## Overview
Scanned and modernized the `web/` codebase using Google Chrome's `modern-web-guidance` suite. Applied modern web standards and eliminated legacy JavaScript and DOM patterns without altering any colors, themes, visual palettes, or CSS design tokens.

## Modernizations Applied
1. **`js/error-cause` (`web/src/export/serverExport.ts`)**:
   - Passed `{ cause: err }` when wrapping exceptions in `new Error(...)`, preserving the original error instance and stack trace across the export pipeline.
2. **`js/abortsignal-timeout` (`web/src/services/exportApi.ts`)**:
   - Added declarative `AbortSignal.timeout(ms)` to fetch requests (`pingHealth`, `initExport`, `uploadSourceAudio`, `finalizeExport`, `pollExportStatus`, `cancelExport`) preventing connection hangs during network delays or container cold starts.
3. **`dialog` & `accessibility` (`web/src/components/modals/ServerExportModal.tsx`)**:
   - Added `role="dialog"`, `aria-modal="true"`, and `aria-labelledby="export-modal-title"` to the modal container.
   - Added `overscroll-behavior: contain` (`overscroll-contain`) to stop scroll chaining to the underlying canvas viewport.
   - Added platform dismiss via the `Escape` key (`platform-controls-dismiss-dialog`) when not in an active encoding phase.
   - Preserved all styling, borders, retro terminal ASCII animations, and color tokens completely intact.
4. **`tabs` & `accessibility` (`web/src/components/panels/ExportDrawer.tsx`)**:
   - Added `role="tablist"` and `role="tab"` with `aria-selected` to the export format tabs (`image`, `text`, `vector`, `clip`).
   - Preserved all tab styling and colors completely intact.

## Verification
- `legacy-scan`: 0 findings across 38 guides / 52 deterministic rules (`npx modern-web-guidance legacy-scan web --json`).
- TypeScript / Vite build: Passed with 0 errors (`npm --prefix web run build`).
- Full Python test suite: 435 tests passed (`pytest tests/ -q`).
