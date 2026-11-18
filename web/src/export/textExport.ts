import { CHAR_PRESETS, DEFAULT_CHAR_ASPECT } from '../store/presets';
import type { RampPreset } from '../types/studio';
import { downloadText } from './download';

export interface AsciiTextOptions {
  cols?: number;
  rampPreset?: RampPreset;
  customChars?: string;
  charAspect?: number;
  filename?: string;
}

/**
 * Generates and downloads a plain ASCII text (.txt) grid from image/video source (MEDIA-03, D-08).
 * Uses exact Rec. 601 luminance weights (0.299*R + 0.587*G + 0.114*B) matching src/renderer.py:49-51.
 */
export function exportAsciiText(
  source: HTMLImageElement | HTMLVideoElement | HTMLCanvasElement,
  options: AsciiTextOptions = {}
): string {
  const chars =
    options.customChars && options.customChars.length > 0
      ? options.customChars
      : CHAR_PRESETS[options.rampPreset ?? 'standard'];

  const cols = options.cols ?? 100;
  const charAspect = options.charAspect ?? DEFAULT_CHAR_ASPECT;

  const srcWidth = 'videoWidth' in source ? source.videoWidth : 'naturalWidth' in source ? source.naturalWidth : source.width;
  const srcHeight = 'videoHeight' in source ? source.videoHeight : 'naturalHeight' in source ? source.naturalHeight : source.height;

  const aspect = srcHeight > 0 && srcWidth > 0 ? srcHeight / srcWidth : 0.5;
  const rows = Math.max(1, Math.floor(cols * aspect * charAspect));

  const offscreen = document.createElement('canvas');
  offscreen.width = cols;
  offscreen.height = rows;
  const ctx = offscreen.getContext('2d', { willReadFrequently: true });
  if (!ctx) {
    throw new Error('Failed to create 2D context for ASCII text export');
  }

  ctx.drawImage(source, 0, 0, cols, rows);
  const imgData = ctx.getImageData(0, 0, cols, rows).data;

  const gradientLen = chars.length - 1;
  const lines: string[] = [];

  for (let y = 0; y < rows; y++) {
    const rowOffset = y * cols * 4;
    let line = '';
    for (let x = 0; x < cols; x++) {
      const idx = rowOffset + x * 4;
      const r = imgData[idx];
      const g = imgData[idx + 1];
      const b = imgData[idx + 2];

      // Rec. 601 perceived luminance: 0.299*R + 0.587*G + 0.114*B
      const lum = Math.floor(0.299 * r + 0.587 * g + 0.114 * b);
      const charIdx = Math.min(Math.max(Math.floor((lum * gradientLen) / 255), 0), gradientLen);
      line += chars[charIdx];
    }
    lines.push(line);
  }

  const result = lines.join('\n');
  const filename = options.filename ?? `ascii-art-${Date.now()}.txt`;
  downloadText(result, filename);
  return result;
}
