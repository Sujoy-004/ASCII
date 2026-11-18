---
id: 20261118-fix-broken-tv-horizontal-lines
type: quick
title: Fix Horizontal Lines (Broken TV Effect) on Video Playback Across Studio Effects
created: 2026-11-18
status: in-progress
files_modified:
  - web/src/engine/Pipeline.ts
  - web/src/store/useStudioStore.ts
  - web/src/components/panels/EffectInspector.tsx
  - web/src/engine/shaders/vhs.ts
---

# Quick Plan: Fix Horizontal Lines (Broken TV Effect) on Video Playback Across Studio Effects

## Objective
Eliminate unwanted oscillating horizontal lines (scanlines), chromatic aberration horizontal color bands, and analog noise that appear across all video playback and effect modes as if looking at a broken TV, while ensuring the dedicated VHS effect mode remains fully functional and tunable with dedicated inspector controls.

## Root Cause
1. `web/src/engine/Pipeline.ts` Stage 4 unconditionally applied `vhsShaderNode` on top of every effect output (`gradedOut`), regardless of whether `this.activeEffect === 'vhs'` or any other effect mode (`ascii`, `dither`, `halftone`, `matrix`, etc.).
2. `web/src/store/useStudioStore.ts` configured non-zero defaults in `DEFAULT_EFFECT_PARAMS`: `vhsScanlineIntensity: 0.2`, `vhsAberration: 0.5`, `vhsNoiseIntensity: 0.1`. When `CenterStage.tsx` mounted, these parameters updated the TSL pipeline uniforms, forcing active moving scanlines (frequency 800) and sinusoidal horizontal chromatic aberration bands (`sin(y * 100 + time * 10) * 0.5`) across all media frames.
3. `web/src/components/panels/EffectInspector.tsx` lacked a `case 'vhs':` block, preventing users from viewing or adjusting VHS effect parameters when selecting the VHS mode.

## Proposed Changes
1. **`web/src/engine/Pipeline.ts`**:
   - In `rebuildPipeline()`, gate Stage 4 post-processing so `vhsShaderNode` is only executed when `this.activeEffect === 'vhs'`.
   - For all other effect modes (`ascii`, `dither`, `halftone`, `matrix`, `dots`, `blockify`, `pixelSort`, etc.), pass `gradedOut` directly to `displayMaterial.colorNode`, ensuring clean, artifact-free presentation.
2. **`web/src/store/useStudioStore.ts`**:
   - Tune `DEFAULT_EFFECT_PARAMS` for VHS mode with realistic retro parameters: `vhsScanlineIntensity: 0.35`, `vhsAberration: 0.1`, `vhsNoiseIntensity: 0.1`, `vhsCurvature: 0.0`.
3. **`web/src/components/panels/EffectInspector.tsx`**:
   - Add `case 'vhs':` offering sliders for Scanline Intensity, Color Glitch (Aberration), Tape Noise, and CRT Curvature so users who explicitly select VHS mode can control the effect.
4. **`web/src/engine/shaders/vhs.ts`**:
   - Ensure subtle chromatic shift and smooth scanlines that behave gracefully when adjusted.

## Verification Plan
1. Build frontend bundle without errors: `npm --prefix web run build`.
2. Run automated test suite: `python -m pytest tests/ -q`.
3. Playwright E2E verification:
   - Upload `assets/videos/test.mp4`.
   - Verify video plays with ASCII effect cleanly with zero horizontal lines or TV distortion.
   - Switch between Dither, Halftone, Matrix, Blockify, and verify no horizontal lines appear.
   - Switch to VHS mode, verify VHS scanlines and effect parameters work and sliders respond.
4. Deploy updated production bundle to Cloudflare Pages (`npm run deploy:web`).
5. Verify live deployment at `https://rgb-ascii.pages.dev`.
