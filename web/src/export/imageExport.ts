import { downloadBlob } from './download';

/**
 * Exports the current canvas buffer as a high-resolution PNG or JPEG file (MEDIA-03).
 * Uses canvas.toBlob() to avoid tainted canvas security issues.
 */
export async function exportRasterImage(
  canvas: HTMLCanvasElement,
  format: 'png' | 'jpeg',
  quality = 0.95,
  filename?: string
): Promise<void> {
  const mimeType = format === 'png' ? 'image/png' : 'image/jpeg';
  const outName = filename ?? `retro-fx-export-${Date.now()}.${format}`;

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error('Failed to create image blob from canvas'));
          return;
        }
        downloadBlob(blob, outName);
        resolve();
      },
      mimeType,
      quality
    );
  });
}
