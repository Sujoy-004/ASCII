import { CHAR_PRESETS, DEFAULT_CHAR_ASPECT } from '../store/presets';
import type { RampPreset } from '../types/studio';
import { downloadText } from './download';

export interface SvgExportOptions {
  cols?: number;
  colorMode?: 'monochrome' | 'truecolor';
  rampPreset?: RampPreset;
  customChars?: string;
  charAspect?: number;
  bgColor?: string;
  fgColor?: string;
  filename?: string;
}

/**
 * Generates and downloads a scalable vector SVG document (MEDIA-03, D-08).
 * Supports lightweight monochrome mode and TrueColor mode with colored <tspan> elements.
 */
export function exportAsciiSvg(
  source: HTMLImageElement | HTMLVideoElement | HTMLCanvasElement,
  options: SvgExportOptions = {}
): string {
  const chars =
    options.customChars && options.customChars.length > 0
      ? options.customChars
      : CHAR_PRESETS[options.rampPreset ?? 'standard'];

  const cols = options.cols ?? 100;
  const colorMode = options.colorMode ?? 'truecolor';
  const charAspect = options.charAspect ?? DEFAULT_CHAR_ASPECT;
  const bgColor = options.bgColor ?? '#0a0a0a';
  const fgColor = options.fgColor ?? '#ffffff';

  const srcWidth = 'videoWidth' in source ? source.videoWidth : 'naturalWidth' in source ? source.naturalWidth : source.width;
  const srcHeight = 'videoHeight' in source ? source.videoHeight : 'naturalHeight' in source ? source.naturalHeight : source.height;

  const aspect = srcHeight > 0 && srcWidth > 0 ? srcHeight / srcWidth : 0.5;
  const rows = Math.max(1, Math.floor(cols * aspect * charAspect));

  const offscreen = document.createElement('canvas');
  offscreen.width = cols;
  offscreen.height = rows;
  const ctx = offscreen.getContext('2d', { willReadFrequently: true });
  if (!ctx) {
    throw new Error('Failed to create 2D context for SVG export');
  }

  ctx.drawImage(source, 0, 0, cols, rows);
  const imgData = ctx.getImageData(0, 0, cols, rows).data;

  const charW = 10;
  const charH = Math.round(charW / charAspect);
  const svgWidth = cols * charW;
  const svgHeight = rows * charH;

  const gradientLen = chars.length - 1;
  const svgParts: string[] = [];

  svgParts.push(`<?xml version="1.0" encoding="UTF-8"?>`);
  svgParts.push(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${svgWidth} ${svgHeight}" width="${svgWidth}" height="${svgHeight}">`
  );
  svgParts.push(`<rect width="100%" height="100%" fill="${bgColor}"/>`);
  svgParts.push(
    `<text font-family="monospace, Courier New, Consolas" font-size="${charH * 0.85}" xml:space="preserve">`
  );

  for (let y = 0; y < rows; y++) {
    const rowY = (y + 1) * charH - Math.round(charH * 0.2);
    const rowOffset = y * cols * 4;

    if (colorMode === 'monochrome') {
      let lineText = '';
      for (let x = 0; x < cols; x++) {
        const idx = rowOffset + x * 4;
        const r = imgData[idx];
        const g = imgData[idx + 1];
        const b = imgData[idx + 2];
        const lum = Math.floor(0.299 * r + 0.587 * g + 0.114 * b);
        const charIdx = Math.min(Math.max(Math.floor((lum * gradientLen) / 255), 0), gradientLen);
        const c = chars[charIdx];
        lineText += c === '&' ? '&amp;' : c === '<' ? '&lt;' : c === '>' ? '&gt;' : c;
      }
      svgParts.push(`<tspan x="0" y="${rowY}" fill="${fgColor}">${lineText}</tspan>`);
    } else {
      let tspans = '';
      for (let x = 0; x < cols; x++) {
        const idx = rowOffset + x * 4;
        const r = imgData[idx];
        const g = imgData[idx + 1];
        const b = imgData[idx + 2];
        const lum = Math.floor(0.299 * r + 0.587 * g + 0.114 * b);
        const charIdx = Math.min(Math.max(Math.floor((lum * gradientLen) / 255), 0), gradientLen);
        const rawC = chars[charIdx];
        const c = rawC === '&' ? '&amp;' : rawC === '<' ? '&lt;' : rawC === '>' ? '&gt;' : rawC;
        const xPos = x * charW;
        tspans += `<tspan x="${xPos}" y="${rowY}" fill="rgb(${r},${g},${b})">${c}</tspan>`;
      }
      svgParts.push(tspans);
    }
  }

  svgParts.push(`</text></svg>`);
  const result = svgParts.join('\n');
  const filename = options.filename ?? `ascii-vector-${Date.now()}.svg`;
  downloadText(result, filename, 'image/svg+xml;charset=utf-8');
  return result;
}
