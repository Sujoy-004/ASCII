/**
 * Client service client for the FastAPI export backend per D-01, D-02, D-03, D-10.
 */

export interface ExportInitPayload {
  format: 'mp4' | 'gif';
  duration: number;
  fps: number;
  turnstile_token?: string | null;
}

export interface ExportInitResponse {
  job_id: string;
  job_token: string;
  state: string;
}

export interface ExportStatusResponse {
  job_id?: string;
  state: 'capturing' | 'uploading' | 'encoding' | 'completed' | 'failed' | 'cancelled' | 'expired';
  progress?: number;
  error?: string | null;
  download_token?: string | null;
  message?: string;
}

export class ServerBusyApiError extends Error {
  public retryAfter: number;

  constructor(message: string, retryAfter = 30) {
    super(message);
    this.name = 'ServerBusyApiError';
    this.retryAfter = retryAfter;
  }
}

// Configurable backend base URL with Render production fallback
const API_BASE = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? 'https://rgb-ascii-api.onrender.com' : 'http://localhost:8000')
).replace(/\/+$/, '');

export const exportApi = {
  /**
   * Health ping for Render container pre-warming per D-04.
   */
  async pingHealth(): Promise<{ status: string; version: string; timestamp: number }> {
    const res = await fetch(`${API_BASE}/api/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) {
      throw new Error(`Health ping failed: HTTP ${res.status}`);
    }
    return res.json();
  },

  /**
   * Initialize export session and acquire concurrency lock per D-02.
   */
  async initExport(payload: ExportInitPayload): Promise<ExportInitResponse> {
    const res = await fetch(`${API_BASE}/api/export/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(20_000),
    });

    if (res.status === 503) {
      const retryHeader = res.headers.get('Retry-After');
      const retryAfter = retryHeader ? parseInt(retryHeader, 10) || 30 : 30;
      let errDetail = 'Server is currently busy encoding another export job.';
      try {
        const body = await res.json();
        if (body.message) errDetail = body.message;
      } catch {
        // ignore JSON parse fail
      }
      throw new ServerBusyApiError(errDetail, retryAfter);
    }

    if (!res.ok) {
      let msg = `Export initialization failed: HTTP ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) msg = errJson.detail;
      } catch {
        // ignore
      }
      throw new Error(msg);
    }

    return res.json();
  },

  /**
   * Upload sequential WebM chunk binary using XMLHttpRequest for live progress telemetry per D-01, D-03.
   */
  uploadChunk(
    jobId: string,
    jobToken: string,
    chunkIndex: number,
    chunkBlob: Blob,
    onProgress?: (loadedBytes: number, totalBytes: number) => void,
  ): Promise<{ status: string; uploaded_bytes: number }> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const url = `${API_BASE}/api/export/${encodeURIComponent(jobId)}/chunk?chunk_index=${chunkIndex}`;

      xhr.open('POST', url, true);
      xhr.setRequestHeader('X-Job-Token', jobToken);
      xhr.setRequestHeader('Content-Type', 'application/octet-stream');

      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = (ev) => {
          if (ev.lengthComputable) {
            onProgress(ev.loaded, ev.total);
          }
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            resolve({ status: 'chunk_received', uploaded_bytes: chunkBlob.size });
          }
        } else {
          let errDetail = `Chunk upload failed (HTTP ${xhr.status})`;
          try {
            const errObj = JSON.parse(xhr.responseText);
            if (errObj.detail) errDetail = errObj.detail;
          } catch {
            // ignore
          }
          reject(new Error(errDetail));
        }
      };

      xhr.onerror = () => {
        reject(new Error('Network error occurred during chunk upload.'));
      };

      xhr.send(chunkBlob);
    });
  },

  /**
   * Upload source audio/video media for server-side fallback seeking muxer per D-05.
   */
  async uploadSourceAudio(
    jobId: string,
    jobToken: string,
    file: File,
    clipStart = 0.0,
    clipDuration = 0.0,
  ): Promise<{ status: string }> {
    const formData = new FormData();
    formData.append('file', file, (file as File).name || 'audio.mp4');

    const res = await fetch(`${API_BASE}/api/export/${encodeURIComponent(jobId)}/source-audio`, {
      method: 'POST',
      headers: {
        'X-Job-Token': jobToken,
        'X-Clip-Start': clipStart.toFixed(3),
        'X-Clip-Duration': clipDuration.toFixed(3),
      },
      body: formData,
      signal: AbortSignal.timeout(60_000),
    });

    if (!res.ok) {
      throw new Error(`Source audio upload failed: HTTP ${res.status}`);
    }

    return res.json();
  },

  /**
   * Finalize chunk upload and transition job into encoding state per D-02.
   */
  async finalizeExport(jobId: string, jobToken: string): Promise<{ status: string; state: string }> {
    const res = await fetch(`${API_BASE}/api/export/${encodeURIComponent(jobId)}/finalize`, {
      method: 'POST',
      headers: {
        'X-Job-Token': jobToken,
        Accept: 'application/json',
      },
      signal: AbortSignal.timeout(20_000),
    });

    if (!res.ok) {
      throw new Error(`Finalize export failed: HTTP ${res.status}`);
    }

    return res.json();
  },

  /**
   * Poll export status with container restart resilience (404 -> expired) per D-02, D-03.
   */
  async pollExportStatus(jobId: string): Promise<ExportStatusResponse> {
    const res = await fetch(`${API_BASE}/api/export/${encodeURIComponent(jobId)}/status`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(10_000),
    });

    if (res.status === 404) {
      return {
        state: 'expired',
        message: 'Server instance restarted or job expired. Please retry.',
      };
    }

    if (!res.ok) {
      throw new Error(`Failed to fetch export status: HTTP ${res.status}`);
    }

    return res.json();
  },

  /**
   * Cancel in-progress export session and release concurrency lock per D-02.
   */
  async cancelExport(jobId: string, jobToken: string): Promise<void> {
    try {
      await fetch(`${API_BASE}/api/export/${encodeURIComponent(jobId)}/cancel`, {
        method: 'POST',
        headers: {
          'X-Job-Token': jobToken,
          Accept: 'application/json',
        },
        signal: AbortSignal.timeout(5_000),
      });
    } catch (err) {
      console.warn('[exportApi] Cancel request error:', err);
    }
  },

  /**
   * Generate download URL using short-lived single-use download token per D-10.
   */
  getDownloadUrl(jobId: string, downloadToken: string): string {
    return `${API_BASE}/api/export/${encodeURIComponent(jobId)}/download?download_token=${encodeURIComponent(downloadToken)}`;
  },
};
