/**
 * Client-side high-resolution canvas capture and chunk upload orchestrator per D-01, D-02, D-03, D-05.
 */

import { getAudioStreamTrack, getOrCreateAudioGraph, resumeAudioContext } from './audioGraph';
import { exportApi, ServerBusyApiError } from '../services/exportApi';
import { getActiveFile, getActiveStream, getRegisteredVideo } from '../store/useStudioStore';

export interface ServerExportOptions {
  format: 'mp4' | 'gif';
  targetResolution: '1080p' | '720p' | '480p';
  targetFps: number;
  durationSec: number;
  turnstileToken?: string | null;
  includeAudio?: boolean;
  onProgress: (
    stage: 1 | 2 | 3 | 4,
    percent: number,
    details?: { fps?: number; speed?: string; bytesUploaded?: number; totalBytes?: number },
  ) => void;
  onStatusChange: (statusText: string) => void;
  onError: (err: Error) => void;
  onComplete: (downloadUrl: string) => void;
}

export interface ActiveExportController {
  cancel: () => Promise<void>;
}

const RESOLUTION_MAP: Record<string, { width: number; height: number; bitrate: number }> = {
  '1080p': { width: 1920, height: 1080, bitrate: 3_500_000 },
  '720p': { width: 1280, height: 720, bitrate: 2_000_000 },
  '480p': { width: 854, height: 480, bitrate: 1_200_000 },
};

/**
 * Negotiate optimal supported video container mime type per D-01.
 */
function negotiateMimeType(): string {
  const candidates = [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
    'video/mp4;codecs=avc1',
  ];
  for (const mime of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(mime)) {
      return mime;
    }
  }
  return 'video/webm';
}

/**
 * Start high-resolution client canvas capture with upload backpressure and server export telemetry per D-01, D-03.
 */
export function startServerExport(options: ServerExportOptions): ActiveExportController {
  let isCancelled = false;
  let activeJobId: string | null = null;
  let activeJobToken: string | null = null;
  let mediaRecorder: MediaRecorder | null = null;

  const run = async () => {
    const {
      format,
      targetResolution,
      targetFps,
      durationSec,
      turnstileToken,
      includeAudio = true,
      onProgress,
      onStatusChange,
      onError,
      onComplete,
    } = options;

    const resConfig = RESOLUTION_MAP[targetResolution] || RESOLUTION_MAP['1080p'];
    const targetWidth = resConfig.width;
    const targetHeight = resConfig.height;
    const targetBitrate = resConfig.bitrate;

    // 1. Locate CenterStage canvas element
    const canvas = document.querySelector('canvas');
    if (!canvas) {
      throw new Error('Canvas element not found in DOM.');
    }

    // 2. Resume AudioContext for user click interaction compliance
    if (includeAudio && format === 'mp4') {
      await resumeAudioContext();
    }

    onStatusChange('Initializing export session on server...');

    // 3. Initialize export session on backend
    let initRes;
    try {
      initRes = await exportApi.initExport({
        format,
        duration: durationSec,
        fps: targetFps,
        turnstile_token: turnstileToken,
      });
    } catch (err) {
      if (err instanceof ServerBusyApiError) {
        throw err;
      }
      throw new Error(`Failed to initialize server export: ${(err as Error).message}`);
    }

    activeJobId = initRes.job_id;
    activeJobToken = initRes.job_token;

    if (isCancelled) return;

    // 4. DPI Decoupling: save interactive dimensions and lock canvas to target resolution per D-01
    const originalWidth = canvas.width;
    const originalHeight = canvas.height;
    const originalStyleWidth = canvas.style.width;
    const originalStyleHeight = canvas.style.height;

    // Set backing-buffer dimensions
    canvas.width = targetWidth;
    canvas.height = targetHeight;

    try {
      // 5. Capture Stream with Target FPS
      const stream = canvas.captureStream(targetFps);

      // Connect audio track if requested and video element is active per D-05
      if (includeAudio && format === 'mp4') {
        const videoEl = getRegisteredVideo();
        if (videoEl && !videoEl.paused) {
          getOrCreateAudioGraph(videoEl);
          const audioTrack = getAudioStreamTrack();
          if (audioTrack) {
            stream.addTrack(audioTrack);
          }
        } else {
          const webcamStream = getActiveStream();
          if (webcamStream) {
            const camAudio = webcamStream.getAudioTracks()[0];
            if (camAudio) stream.addTrack(camAudio);
          }
        }
      }

      // 6. Negotiate Codec and configure MediaRecorder
      const mimeType = negotiateMimeType();
      mediaRecorder = new MediaRecorder(stream, {
        mimeType,
        videoBitsPerSecond: targetBitrate,
      });

      // Bounded chunk queue & backpressure state per D-01
      const chunkQueue: { index: number; blob: Blob }[] = [];
      let nextChunkIndex = 0;
      let totalBytesUploaded = 0;
      let totalRecordedBytes = 0;
      let isUploading = false;
      let recordingFinished = false;

      // Stage 1 telemetry: Frame capture tracking
      const startTime = performance.now();
      const targetDurationMs = durationSec * 1000;

      const progressInterval = window.setInterval(() => {
        if (recordingFinished || isCancelled) return;
        const elapsed = performance.now() - startTime;
        const capturePct = Math.min(1.0, elapsed / targetDurationMs);
        onProgress(1, capturePct);
      }, 100);

      const processUploadQueue = async () => {
        if (isUploading || isCancelled) return;
        isUploading = true;

        while (chunkQueue.length > 0 && !isCancelled) {
          const chunk = chunkQueue.shift()!;
          try {
            await exportApi.uploadChunk(
              activeJobId!,
              activeJobToken!,
              chunk.index,
              chunk.blob,
              (_loaded, _total) => {
                const currentChunkBytes = totalBytesUploaded + _loaded;
                const uploadPct = totalRecordedBytes > 0
                  ? Math.min(1.0, currentChunkBytes / totalRecordedBytes)
                  : 0.5;
                onProgress(2, uploadPct, {
                  bytesUploaded: currentChunkBytes,
                  totalBytes: totalRecordedBytes,
                });
              },
            );
            totalBytesUploaded += chunk.blob.size;
          } catch (uploadErr) {
            console.error('[serverExport] Chunk upload error:', uploadErr);
            throw uploadErr;
          }

          // Backpressure release: resume recording when queue drains to 2 per D-01
          if (
            mediaRecorder &&
            mediaRecorder.state === 'paused' &&
            chunkQueue.length <= 2 &&
            !recordingFinished
          ) {
            mediaRecorder.resume();
          }
        }

        isUploading = false;
      };

      mediaRecorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0 && !isCancelled) {
          const chunkBlob = event.data;
          totalRecordedBytes += chunkBlob.size;

          // 35 MB cumulative upload ceiling check per D-01
          if (totalRecordedBytes > 35 * 1024 * 1024) {
            mediaRecorder?.stop();
            throw new Error('Export exceeded maximum upload ceiling of 35 MB.');
          }

          chunkQueue.push({ index: nextChunkIndex++, blob: chunkBlob });

          // Bounded backpressure: pause if in-flight queue reaches 5 chunks per D-01
          if (chunkQueue.length >= 5 && mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.pause();
          }

          processUploadQueue().catch(onError);
        }
      };

      // 7. Start recording in 1000ms slices per D-01
      mediaRecorder.start(1000);
      onStatusChange('Capturing high-resolution canvas frames (Stage 1)...');

      // Wait until target duration elapses
      await new Promise<void>((resolve) => {
        window.setTimeout(() => {
          recordingFinished = true;
          window.clearInterval(progressInterval);
          onProgress(1, 1.0);
          if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
          }
          resolve();
        }, targetDurationMs);
      });

      if (isCancelled) return;

      onStatusChange('Finalizing chunk uploads (Stage 2)...');

      // Wait for any remaining chunks in upload queue to drain
      while ((chunkQueue.length > 0 || isUploading) && !isCancelled) {
        await new Promise((r) => window.setTimeout(r, 100));
      }

      onProgress(2, 1.0, { bytesUploaded: totalRecordedBytes, totalBytes: totalRecordedBytes });

      // Optional: upload pristine source media for audio fallback seeking per D-05
      const sourceFile = getActiveFile();
      if (sourceFile && format === 'mp4' && includeAudio && !isCancelled) {
        try {
          onStatusChange('Uploading pristine source audio fallback...');
          const videoEl = getRegisteredVideo();
          const clipStart = videoEl ? videoEl.currentTime : 0.0;
          await exportApi.uploadSourceAudio(activeJobId!, activeJobToken!, sourceFile, clipStart, durationSec);
        } catch (audioErr) {
          console.warn('[serverExport] Fallback audio upload non-fatal warning:', audioErr);
        }
      }

      if (isCancelled) return;

      // 8. Finalize export and trigger server-side encoding
      onStatusChange('Triggering FFmpeg server transcode (Stage 3)...');
      await exportApi.finalizeExport(activeJobId!, activeJobToken!);

      // 9. Poll server status until completion per D-03
      let pollCount = 0;
      let downloadUrl = '';

      while (!isCancelled) {
        await new Promise((r) => window.setTimeout(r, 1500));
        pollCount++;

        const status = await exportApi.pollExportStatus(activeJobId!);

        if (status.state === 'encoding') {
          const encPct = status.progress || 0.0;
          onProgress(3, encPct);
          onStatusChange(`Encoding on server (${Math.round(encPct * 100)}%)...`);
        } else if (status.state === 'completed') {
          onProgress(3, 1.0);
          onProgress(4, 1.0);
          onStatusChange('Export ready for download (Stage 4)!');
          const dlToken = status.download_token || '';
          downloadUrl = exportApi.getDownloadUrl(activeJobId!, dlToken);
          onComplete(downloadUrl);
          break;
        } else if (status.state === 'failed') {
          throw new Error(`Server export failed: ${status.error || 'Unknown transcode error'}`);
        } else if (status.state === 'expired') {
          throw new Error('Server instance restarted or job expired. Please retry.');
        }

        // Safety timeout: 10 minutes maximum polling
        if (pollCount > 400) {
          throw new Error('Server export timed out waiting for encoding completion.');
        }
      }
    } finally {
      // 10. Restore canvas dimensions and pixel ratio in all cases per D-01
      canvas.width = originalWidth;
      canvas.height = originalHeight;
      canvas.style.width = originalStyleWidth;
      canvas.style.height = originalStyleHeight;
    }
  };

  run().catch((err) => {
    if (!isCancelled) {
      options.onError(err);
    }
  });

  return {
    cancel: async () => {
      isCancelled = true;
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        try {
          mediaRecorder.stop();
        } catch {
          // ignore
        }
      }
      if (activeJobId && activeJobToken) {
        await exportApi.cancelExport(activeJobId, activeJobToken);
      }
    },
  };
}
