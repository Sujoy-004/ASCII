// @ts-expect-error gifenc exports ESM from dist/gifenc.esm.js
import { GIFEncoder, quantize, applyPalette } from 'gifenc';
import { downloadBlob } from './download';

export interface VideoRecordProgress {
  pct: number;
  message: string;
}

/**
 * Records a short WebM video clip directly from the canvas via MediaRecorder (D-08).
 */
export async function recordWebmClip(
  canvas: HTMLCanvasElement,
  durationSeconds = 3,
  onProgress?: (progress: VideoRecordProgress) => void,
  filename?: string
): Promise<Blob> {
  const stream = canvas.captureStream(30);

  const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
    ? 'video/webm;codecs=vp9'
    : MediaRecorder.isTypeSupported('video/webm')
    ? 'video/webm'
    : '';

  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks: Blob[] = [];

  return new Promise((resolve, reject) => {
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };

    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: 'video/webm' });
      const outName = filename ?? `retro-clip-${Date.now()}.webm`;
      downloadBlob(blob, outName);
      if (onProgress) onProgress({ pct: 100, message: 'Done' });
      resolve(blob);
    };

    recorder.onerror = (e) => {
      reject(e);
    };

    recorder.start(100);
    const start = performance.now();
    const intervalMs = 100;

    const timer = setInterval(() => {
      const elapsed = (performance.now() - start) / 1000;
      const pct = Math.min(Math.round((elapsed / durationSeconds) * 100), 99);
      if (onProgress) onProgress({ pct, message: `Recording WebM... ${pct}%` });

      if (elapsed >= durationSeconds) {
        clearInterval(timer);
        recorder.stop();
      }
    }, intervalMs);
  });
}

/**
 * Records an animated GIF client-side using gifenc without server roundtrips (D-08).
 * Limits duration to 5 seconds to prevent browser memory exhaustion (T-02-10).
 */
export async function recordGifClip(
  canvas: HTMLCanvasElement,
  durationSeconds = 2,
  fps = 10,
  onProgress?: (progress: VideoRecordProgress) => void,
  filename?: string
): Promise<Blob> {
  const safeDuration = Math.min(Math.max(durationSeconds, 1), 5); // T-02-10 guard: 1..5 seconds max
  const totalFrames = Math.round(safeDuration * fps);
  const delay = Math.round(1000 / fps);

  const width = canvas.width;
  const height = canvas.height;

  const gif = GIFEncoder();
  const offscreen = document.createElement('canvas');
  offscreen.width = width;
  offscreen.height = height;
  const ctx = offscreen.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('Failed to get 2D context for GIF recording');

  for (let f = 0; f < totalFrames; f++) {
    ctx.drawImage(canvas, 0, 0, width, height);
    const imgData = ctx.getImageData(0, 0, width, height).data;

    // Quantize palette to 256 colors
    const palette = quantize(imgData, 256);
    const index = applyPalette(imgData, palette);

    gif.writeFrame(index, width, height, { palette, delay });

    const pct = Math.round(((f + 1) / totalFrames) * 100);
    if (onProgress) onProgress({ pct, message: `Encoding GIF... ${pct}%` });

    await new Promise((r) => setTimeout(r, delay));
  }

  gif.finish();
  const bytes = gif.bytes();
  const blob = new Blob([bytes], { type: 'image/gif' });
  const outName = filename ?? `retro-animation-${Date.now()}.gif`;
  downloadBlob(blob, outName);
  return blob;
}
