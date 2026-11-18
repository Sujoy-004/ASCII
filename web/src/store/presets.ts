/**
 * Character ramp presets and Rec. 601 perceptual luminance weights.
 * Presets are copied directly from src/config.py:13-26 for 1:1 cross-platform fidelity.
 */
import type { RampPreset } from '../types/studio';

export const DEFAULT_CHARS = ' .:-=+*#%@';

export const CHAR_PRESETS: Record<RampPreset, string> = {
  standard: DEFAULT_CHARS,
  // Dense: many grayscale ramps, subtle midtone steps (classic 10-step).
  dense: ' .\'`^",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$',
  // Simple: a coarse but instantly readable low-value ramp.
  simple: ' .:-=+*#%@',
  // Blocks: filled block elements for high-contrast monochrome rendering.
  blocks: ' \u2591\u2592\u2593\u2588',
};

/** Rec. 601 perceptual luminance weights (src/renderer.py:49-51). */
export const REC601_WEIGHTS = {
  r: 0.299,
  g: 0.587,
  b: 0.114,
} as const;

/** Aspect ratio of monospace characters (width / height, default 0.5). */
export const DEFAULT_CHAR_ASPECT = 0.5;
