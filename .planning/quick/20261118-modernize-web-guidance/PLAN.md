---
id: 20261118-modernize-web-guidance
type: quick
title: Modernize Web Platform Patterns via Google Chrome Modern Web Guidance
created: 2026-11-18
status: in-progress
files_modified:
  - web/src/export/serverExport.ts
  - web/src/services/exportApi.ts
  - web/src/components/modals/ServerExportModal.tsx
  - web/src/components/panels/ExportDrawer.tsx
---

# Quick Plan: Modernize Web Platform Patterns via Google Chrome Modern Web Guidance

## Objective
Apply modern web platform patterns and standards from the newly installed `GoogleChrome/modern-web-guidance` plugin across the `web/` application without altering any user-facing color choices, palettes, or visual styles.

## Proposed Changes
1. **`web/src/export/serverExport.ts`**:
   - Apply `js/error-cause`: Pass `{ cause: err }` when wrapping exceptions in `new Error(...)` to preserve error stacks and cause chaining across the export pipeline.
2. **`web/src/services/exportApi.ts`**:
   - Apply `js/abortsignal-timeout`: Use declarative `AbortSignal.timeout(ms)` on fetch requests (health check, init, status, finalize) to prevent unbounded HTTP hangs without custom timeout bookkeeping.
   - Apply `js/error-cause`: Preserve error cause objects on network failures.
3. **`web/src/components/modals/ServerExportModal.tsx`**:
   - Apply `dialog` and `accessibility` guidelines:
     - Add `role="dialog" aria-modal="true" aria-labelledby="export-modal-title"` to modal overlay container.
     - Add `overscroll-behavior: contain` (`overscroll-contain`) to stop scroll chaining to the underlying canvas viewport during modal display.
     - Add `Escape` key listener (`platform-controls-dismiss-dialog`) to allow safe platform dismissal when not in active transcoding phase.
     - Strict constraint: preserve all existing colors (`border-border`, `bg-raised`, `text-control`, `text-highlight`, `emerald`, `amber`, etc.) completely unchanged.
4. **`web/src/components/panels/ExportDrawer.tsx`**:
   - Apply `accessibility` & `tabs` guidelines:
     - Add `role="tablist"` and `role="tab"` with `aria-selected` to the 4 export subtabs (`image`, `text`, `vector`, `clip`).
     - Strict constraint: preserve all existing colors, classes, and layouts completely unchanged.

## Verification Plan
1. Re-run `npx modern-web-guidance legacy-scan web --json` to verify 0 legacy rule violations.
2. Verify TypeScript strict type check and build: `npm --prefix web run build`.
3. Verify backend Python test suite regression: `python -m pytest tests/ -q`.
