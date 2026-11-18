/**
 * Studio type contracts — phase 02-02.
 * SHADER-01: charSpacing in [0, 8] px; SHADER-03: hueRotation in [-180, 180] degrees.
 * charAspect mirrors `char_aspect = 0.5` from src/config.py (Rec. 601 pipeline).
 */

export type MediaType = 'image' | 'video' | 'webcam';

export type ThemeMode = 'dark' | 'light';

/** The 16 Grainrad effect modes (D-02). */
export type EffectMode =
  | 'ascii'
  | 'dither'
  | 'halftone'
  | 'vhs'
  | 'matrix'
  | 'dots'
  | 'contour'
  | 'pixelSort'
  | 'blockify'
  | 'threshold'
  | 'edgeDetect'
  | 'crosshatch'
  | 'waveLines'
  | 'noise'
  | 'voronoi'
  | 'tone';

export type RampPreset = 'standard' | 'dense' | 'simple' | 'blocks';

/** Pre-tone adjustments applied before the primary effect (SHADER-03, D-06 stage 1). */
export interface ToneSettings {
  /** 0..2, 1 = neutral */
  brightness: number;
  /** 0..2, 1 = neutral */
  contrast: number;
  /** 0..2, 1 = neutral */
  saturation: number;
  /** [-180, 180] degrees (SHADER-03) */
  hueRotation: number;
  /** 0.1..3, 1 = neutral */
  gamma: number;
  invert: boolean;
}

/** ASCII engine parameters (SHADER-01, D-07). */
export interface AsciiSettings {
  /** Base cell size in px */
  cellScale: number;
  /** [0, 8] px extra spacing between character cells (SHADER-01) */
  charSpacing: number;
  /** Cell width/height ratio, default 0.5 (monospace glyphs are taller than wide) */
  charAspect: number;
  rampPreset: RampPreset;
  /** Freeform custom ramp (lowest luminance first); overrides rampPreset when non-empty */
  customChars: string;
}

export interface Dimensions {
  width: number;
  height: number;
}

/** Export targets for the client-side export suite (D-08). */
export type ExportFormat = 'png' | 'jpeg' | 'svg' | 'txt' | 'gif' | 'webm';

export interface ExportConfig {
  format: ExportFormat;
  /** Output scale multiplier relative to media native dimensions */
  scale: number;
}
