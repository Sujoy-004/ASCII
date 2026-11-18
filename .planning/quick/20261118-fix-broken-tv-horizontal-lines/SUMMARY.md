---
id: 20261118-fix-broken-tv-horizontal-lines
type: quick
title: Fix Horizontal Scanlines and Broken TV Artifacts on Video Playback Across Studio Effects
created: 2026-11-18
completed: 2026-11-18
status: complete
files_modified:
  - web/src/engine/Pipeline.ts
  - web/src/store/useStudioStore.ts
  - web/src/components/panels/EffectInspector.tsx
  - web/src/engine/shaders/vhs.ts
---

# Quick Task Summary: Fix Horizontal Scanlines and Broken TV Artifacts on Video Playback Across Studio Effects

## 1. Problem Diagnosis
- **Symptom**: When uploading any video to the studio, horizontal oscillating lines ("as if it is an old broken TV") and color bands covered the canvas viewport regardless of the selected effect mode (`ascii`, `dither`, `halftone`, etc.).
- **Root Cause**:
  1. `web/src/engine/Pipeline.ts` Stage 4 unconditionally applied `vhsShaderNode` on top of all shader output passes (`colorNode: gradedOut`), rather than gating it to when VHS effect mode is actively selected.
  2. `web/src/store/useStudioStore.ts` had non-zero defaults in `DEFAULT_EFFECT_PARAMS` (`vhsScanlineIntensity: 0.2`, `vhsAberration: 0.5`, `vhsNoiseIntensity: 0.1`). On app initialization, these non-zero parameters were dispatched to the TSL pipeline uniforms, forcing moving scanlines (`scanlineFrequency: 800`) and high-frequency sinusoidal chromatic aberration bands (`sin(y * 100 + time * 10) * 0.5`) on every single frame.
  3. `web/src/components/panels/EffectInspector.tsx` had no `case 'vhs':` block, so selecting VHS mode displayed no controls to tune or inspect VHS parameters.

## 2. Action Taken
- **`web/src/engine/Pipeline.ts`**:
  - Gated Stage 4 post-processing: `vhsShaderNode` is now executed strictly when `this.activeEffect === 'vhs'`.
  - For all other modes (`ascii`, `dither`, `halftone`, `matrix`, `dots`, `contour`, `pixelSort`, `blockify`, etc.), `gradedOut` is assigned directly to `displayMaterial.colorNode`, producing clean, artifact-free video frames.
- **`web/src/store/useStudioStore.ts`**:
  - Configured balanced default VHS parameters (`vhsScanlineIntensity: 0.35`, `vhsAberration: 0.1`, `vhsNoiseIntensity: 0.1`, `vhsCurvature: 0.0`) so that when users select VHS mode, the effect is authentic without blown-out color banding.
- **`web/src/components/panels/EffectInspector.tsx`**:
  - Added interactive parameter sliders for VHS mode: Scanline Intensity, Color Glitch (Aberration), Tape Noise, and CRT Curvature.
- **`web/src/engine/shaders/vhs.ts`**:
  - Clamped RGB chromatic shift to `[0.0, 1.0]` to prevent channel clipping during extreme glitch parameters.
- **Deployment**:
  - Compiled production bundle: `npm --prefix web run build`.
  - Deployed to Cloudflare Pages: `npx wrangler pages deploy web/dist --project-name=rgb-ascii`.

## 3. Verification
- **Automated Tests**: 435 unit and integration tests passing (`python -m pytest tests/ -q`).
- **TypeScript Compilation**: `tsc --noEmit && vite build` passed cleanly with 0 errors.
- **Playwright E2E**:
  - Uploaded `test.mp4` on live site `https://rgb-ascii.pages.dev/`.
  - Confirmed `ascii`, `dither`, `halftone`, `matrix` play video smoothly with zero horizontal lines or TV distortion.
  - Confirmed `vhs` mode properly activates retro scanlines and responds to inspector sliders.
