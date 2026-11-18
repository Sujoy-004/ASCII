import { useEffect, useRef, useState } from 'react';
import TurnstileWidget from '../ui/TurnstileWidget';
import { exportApi, ServerBusyApiError } from '../../services/exportApi';
import { startServerExport } from '../../export/serverExport';
import type { ActiveExportController } from '../../export/serverExport';

export interface ServerExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultFormat?: 'mp4' | 'gif';
}

type EngineStatus = 'standby' | 'waking' | 'ready';
type ExportPhase = 'config' | 'exporting' | 'completed' | 'busy' | 'error';

const BACKOFF_DELAYS = [0, 3000, 7000, 13000, 21000, 31000, 45000, 60000];

function generateAsciiProgressBar(percent: number, width = 24): string {
  const p = Math.max(0, Math.min(1, percent));
  const completed = Math.round(p * width);
  const remaining = width - completed;
  const bar = '='.repeat(Math.max(0, completed - 1)) + (completed > 0 ? '>' : '') + '-'.repeat(remaining);
  return `[${bar.slice(0, width)}] ${Math.round(p * 100)}%`;
}

export default function ServerExportModal({
  isOpen,
  onClose,
  defaultFormat = 'mp4',
}: ServerExportModalProps) {
  const [format, setFormat] = useState<'mp4' | 'gif'>(defaultFormat);
  const [resolution, setResolution] = useState<'1080p' | '720p' | '480p'>('1080p');
  const [duration, setDuration] = useState(10);
  const [fps, setFps] = useState(30);
  const [includeAudio, setIncludeAudio] = useState(true);

  // Engine pre-warming status per D-04
  const [engineStatus, setEngineStatus] = useState<EngineStatus>('standby');
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);

  // Export lifecycle state
  const [phase, setPhase] = useState<ExportPhase>('config');
  const [currentStage, setCurrentStage] = useState<1 | 2 | 3 | 4>(1);
  const [stageProgress, setStageProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [busyCountdown, setBusyCountdown] = useState(30);
  const [expireCountdown, setExpireCountdown] = useState(600); // 10 minutes

  const [telemetry, setTelemetry] = useState<{ fps?: number; speed?: string; bytesUploaded?: number }>({});
  const controllerRef = useRef<ActiveExportController | null>(null);
  const isMountedRef = useRef(true);

  // Synchronize default format when changed from parent
  useEffect(() => {
    setFormat(defaultFormat);
    if (defaultFormat === 'gif') {
      setResolution('720p');
      setFps(12);
      setDuration(5);
    } else {
      setResolution('1080p');
      setFps(30);
      setDuration(10);
    }
  }, [defaultFormat]);

  // Intent-driven container pre-warming with exponential backoff per D-04
  useEffect(() => {
    if (!isOpen) {
      setEngineStatus('standby');
      return;
    }

    isMountedRef.current = true;
    let attempt = 0;
    let timerId: number | null = null;

    const ping = async () => {
      if (!isMountedRef.current) return;
      setEngineStatus('waking');
      try {
        await exportApi.pingHealth();
        if (isMountedRef.current) {
          setEngineStatus('ready');
        }
      } catch {
        if (!isMountedRef.current) return;
        attempt++;
        if (attempt < BACKOFF_DELAYS.length) {
          timerId = window.setTimeout(ping, BACKOFF_DELAYS[attempt]);
        } else {
          setEngineStatus('standby');
        }
      }
    };

    ping();

    return () => {
      isMountedRef.current = false;
      if (timerId) window.clearTimeout(timerId);
    };
  }, [isOpen]);

  // 10-minute download expiration countdown
  useEffect(() => {
    if (phase !== 'completed') return;
    setExpireCountdown(600);
    const interval = window.setInterval(() => {
      setExpireCountdown((prev) => {
        if (prev <= 1) {
          window.clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => window.clearInterval(interval);
  }, [phase]);

  if (!isOpen) return null;

  const handleStartExport = () => {
    setPhase('exporting');
    setCurrentStage(1);
    setStageProgress(0);
    setErrorMessage(null);
    setStatusMessage('Initiating high-resolution export pipeline...');

    const ctrl = startServerExport({
      format,
      targetResolution: resolution,
      targetFps: fps,
      durationSec: duration,
      turnstileToken,
      includeAudio: format === 'mp4' && includeAudio,
      onProgress: (stage, pct, details) => {
        setCurrentStage(stage);
        setStageProgress(pct);
        if (details) {
          setTelemetry((prev) => ({ ...prev, ...details }));
        }
      },
      onStatusChange: (text) => setStatusMessage(text),
      onComplete: (url) => {
        setDownloadUrl(url);
        setPhase('completed');
        setStatusMessage('Export finished successfully.');
      },
      onError: (err) => {
        if (err instanceof ServerBusyApiError) {
          setPhase('busy');
          setBusyCountdown(err.retryAfter);
          const interval = window.setInterval(() => {
            setBusyCountdown((prev) => {
              if (prev <= 1) {
                window.clearInterval(interval);
                setPhase('config');
                return 0;
              }
              return prev - 1;
            });
          }, 1000);
        } else {
          setPhase('error');
          setErrorMessage(err.message || 'Export failed unexpectedly.');
        }
      },
    });

    controllerRef.current = ctrl;
  };

  const handleCancel = async () => {
    if (controllerRef.current) {
      await controllerRef.current.cancel();
      controllerRef.current = null;
    }
    setPhase('config');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono select-none">
      <div className="flex w-full max-w-lg flex-col border border-border bg-raised text-control shadow-2xl">
        {/* Terminal Title Bar */}
        <div className="flex h-8 items-center justify-between border-b border-border bg-active px-3">
          <div className="flex items-center gap-2">
            <span className="text-highlight font-bold">▲ HIGH-RES EXPORT STUDIO</span>
            <span className="text-dim text-[11px]">v1.0-render</span>
          </div>
          {/* Pre-warming status pill per D-04 */}
          <div className="flex items-center gap-1.5 text-[11px]">
            {engineStatus === 'ready' && (
              <span className="flex items-center gap-1 text-emerald-400">
                <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                Engine: Ready
              </span>
            )}
            {engineStatus === 'waking' && (
              <span className="flex items-center gap-1 text-amber-400">
                <span className="inline-block h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                Engine: Waking (~30s)...
              </span>
            )}
            {engineStatus === 'standby' && (
              <span className="flex items-center gap-1 text-dim">
                <span className="inline-block h-2 w-2 rounded-full bg-dim" />
                Engine: Standby
              </span>
            )}
            <button
              type="button"
              onClick={handleCancel}
              className="ml-3 text-dim hover:text-highlight"
            >
              [X]
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex flex-col gap-4 p-4 text-xs">
          {phase === 'config' && (
            <>
              {/* Format selection */}
              <div className="flex flex-col gap-1.5">
                <span className="text-dim uppercase text-[10px] tracking-wider">Format & Pipeline</span>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setFormat('mp4');
                      setResolution('1080p');
                      setFps(30);
                      setDuration(10);
                    }}
                    className={`h-8 border px-3 text-left transition-colors ${
                      format === 'mp4'
                        ? 'border-highlight bg-active text-highlight'
                        : 'border-border bg-raised text-dim hover:text-base'
                    }`}
                  >
                    <div className="font-bold">MP4 Video (H.264)</div>
                    <div className="text-[10px] opacity-70">Up to 1080p HD with Sync Audio</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setFormat('gif');
                      setResolution('720p');
                      setFps(12);
                      setDuration(5);
                    }}
                    className={`h-8 border px-3 text-left transition-colors ${
                      format === 'gif'
                        ? 'border-highlight bg-active text-highlight'
                        : 'border-border bg-raised text-dim hover:text-base'
                    }`}
                  >
                    <div className="font-bold">Animated GIF</div>
                    <div className="text-[10px] opacity-70">Two-pass 128-color Bayer Dither</div>
                  </button>
                </div>
              </div>

              {/* Resolution & FPS */}
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <span className="text-dim uppercase text-[10px] tracking-wider">Resolution</span>
                  <select
                    value={resolution}
                    onChange={(e) => setResolution(e.target.value as '1080p' | '720p' | '480p')}
                    className="h-7 border border-border bg-active px-2 text-highlight focus:outline-none"
                  >
                    {format === 'mp4' && <option value="1080p">1080p (1920x1080)</option>}
                    <option value="720p">720p (1280x720)</option>
                    <option value="480p">480p (854x480)</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-dim uppercase text-[10px] tracking-wider">Framerate (FPS)</span>
                  <select
                    value={fps}
                    onChange={(e) => setFps(Number(e.target.value))}
                    className="h-7 border border-border bg-active px-2 text-highlight focus:outline-none"
                  >
                    {format === 'mp4' ? (
                      <>
                        <option value={30}>30 FPS (Standard)</option>
                        <option value={60}>60 FPS (Fluid)</option>
                        <option value={24}>24 FPS (Cinematic)</option>
                      </>
                    ) : (
                      <>
                        <option value={12}>12 FPS (Recommended)</option>
                        <option value={15}>15 FPS (High)</option>
                        <option value={10}>10 FPS (Compact)</option>
                      </>
                    )}
                  </select>
                </div>
              </div>

              {/* Duration Slider */}
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between text-dim">
                  <span className="uppercase text-[10px] tracking-wider">Duration</span>
                  <span className="text-highlight font-bold">{duration} seconds</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={format === 'gif' ? 15 : 60}
                  step={1}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="h-3 w-full cursor-ew-resize accent-highlight"
                />
                <div className="flex justify-between text-[10px] text-dim">
                  <span>1s</span>
                  <span>Max {format === 'gif' ? '15s (GIF ceiling)' : '60s (Video ceiling)'}</span>
                </div>
              </div>

              {/* Audio Toggle for MP4 */}
              {format === 'mp4' && (
                <label className="flex items-center gap-2 text-dim hover:text-base cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeAudio}
                    onChange={(e) => setIncludeAudio(e.target.checked)}
                    className="accent-highlight"
                  />
                  <span>Preserve & Synchronize Audio (Web Audio Graph + Fallback)</span>
                </label>
              )}

              {/* Turnstile Bot Verification Widget per D-10 */}
              <TurnstileWidget
                onSuccess={(token) => setTurnstileToken(token)}
                onError={(err) => console.warn('[Turnstile]', err)}
              />

              {/* Action Buttons */}
              <div className="mt-2 flex justify-end gap-2 border-t border-border pt-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="h-7 border border-border px-3 text-dim hover:text-base"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleStartExport}
                  className="h-7 border border-highlight bg-active px-4 text-highlight font-bold hover:bg-highlight hover:text-black transition-colors"
                >
                  Start Export
                </button>
              </div>
            </>
          )}

          {phase === 'exporting' && (
            <div className="flex flex-col gap-3 py-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-highlight uppercase tracking-wider">
                  Stage {currentStage}/4: {
                    currentStage === 1 ? 'Capturing Canvas Frames' :
                    currentStage === 2 ? 'Uploading Stream Chunks' :
                    currentStage === 3 ? 'FFmpeg Server Transcoding' :
                    'Packaging Media File'
                  }
                </span>
                <span className="text-dim text-[11px] tabular-nums">
                  {Math.round(stageProgress * 100)}%
                </span>
              </div>

              {/* ASCII Progress Bar per D-03 */}
              <div className="border border-border bg-black/40 p-2 text-highlight text-center text-sm font-bold tracking-widest overflow-hidden">
                {generateAsciiProgressBar(stageProgress)}
              </div>

              {/* Telemetry readouts from -progress pipe:1 per D-03 */}
              <div className="grid grid-cols-3 gap-2 border border-border bg-active/40 p-2 text-[11px]">
                <div>
                  <div className="text-dim text-[9px] uppercase">Format</div>
                  <div className="text-highlight font-bold">{format.toUpperCase()} ({resolution})</div>
                </div>
                <div>
                  <div className="text-dim text-[9px] uppercase">Encoding Speed</div>
                  <div className="text-highlight font-bold">{telemetry.speed || '1.0x'}</div>
                </div>
                <div>
                  <div className="text-dim text-[9px] uppercase">Telemetry FPS</div>
                  <div className="text-highlight font-bold">{telemetry.fps ? telemetry.fps.toFixed(1) : `${fps}.0`}</div>
                </div>
              </div>

              {/* Status log message */}
              <div className="text-dim text-[11px] flex items-center gap-2">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-highlight animate-ping" />
                {statusMessage}
              </div>

              <div className="mt-2 flex justify-end border-t border-border pt-3">
                <button
                  type="button"
                  onClick={handleCancel}
                  className="h-7 border border-red-500/50 text-red-400 hover:bg-red-500/20 px-3 transition-colors"
                >
                  Cancel Export
                </button>
              </div>
            </div>
          )}

          {phase === 'busy' && (
            <div className="flex flex-col items-center justify-center gap-3 py-6 text-center">
              <div className="text-amber-400 font-bold text-sm">⚠ SERVER CAPACITY CONCURRENT LIMIT</div>
              <p className="text-dim text-xs max-w-sm">
                The single-worker export engine is currently encoding another media job.
                Admission retry in <span className="text-highlight font-bold">{busyCountdown}s</span>...
              </p>
              <button
                type="button"
                onClick={() => setPhase('config')}
                className="mt-2 h-7 border border-border px-3 text-dim hover:text-base"
              >
                Back to Settings
              </button>
            </div>
          )}

          {phase === 'error' && (
            <div className="flex flex-col items-center justify-center gap-3 py-4 text-center">
              <div className="text-red-400 font-bold text-sm">✖ EXPORT PIPELINE ERROR</div>
              <p className="text-dim text-xs max-w-sm bg-black/40 border border-border p-2">
                {errorMessage}
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setPhase('config')}
                  className="h-7 border border-border px-3 text-dim hover:text-base"
                >
                  Retry Settings
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="h-7 border border-border px-3 text-dim hover:text-base"
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {phase === 'completed' && downloadUrl && (
            <div className="flex flex-col gap-3 py-2">
              <div className="flex items-center gap-2 text-emerald-400 font-bold">
                <span>✔ EXPORT READY FOR DOWNLOAD</span>
              </div>
              <div className="border border-border bg-black/40 p-3 text-xs flex flex-col gap-1.5">
                <div className="flex justify-between">
                  <span className="text-dim">Format:</span>
                  <span className="text-highlight font-bold">{format.toUpperCase()} ({resolution})</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-dim">Duration:</span>
                  <span className="text-highlight font-bold">{duration}s @ {fps}fps</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-dim">Artifact Expiration:</span>
                  <span className="text-amber-400 font-bold">{Math.floor(expireCountdown / 60)}m {expireCountdown % 60}s</span>
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t border-border pt-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="h-7 border border-border px-3 text-dim hover:text-base"
                >
                  Done
                </button>
                <a
                  href={downloadUrl}
                  download={`export_${format}.${format}`}
                  className="flex items-center h-7 border border-highlight bg-active px-4 text-highlight font-bold hover:bg-highlight hover:text-black transition-colors"
                >
                  Download Media File
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
