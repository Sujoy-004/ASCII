import type { ReactNode } from 'react';
import { Minus, Plus, Sun, Moon, Play, Pause, Square, Volume2, VolumeX, X } from 'lucide-react';
import { useStudioStore, ZOOM_MAX, ZOOM_MIN } from '../../store/useStudioStore';

const ZOOM_STEP = 1.25;

function formatTime(sec: number): string {
  if (!sec || isNaN(sec) || !isFinite(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

/**
 * Floating viewport HUD pinned bottom-center of Center Stage (STUDIO-03):
 * Video playback (Play/Pause, Stop, Mute/Unmute, Time),
 * [-] [100%] [+] [Reset], native media dimensions, Eject button, dark/light theme toggle.
 */
export default function ViewportHUD() {
  const zoom = useStudioStore((s) => s.zoom);
  const setZoom = useStudioStore((s) => s.setZoom);
  const resetHUD = useStudioStore((s) => s.resetHUD);
  const dimensions = useStudioStore((s) => s.dimensions);
  const mediaType = useStudioStore((s) => s.mediaType);
  const theme = useStudioStore((s) => s.theme);
  const toggleTheme = useStudioStore((s) => s.toggleTheme);
  const isPlaying = useStudioStore((s) => s.isPlaying);
  const isMuted = useStudioStore((s) => s.isMuted);
  const playbackTime = useStudioStore((s) => s.playbackTime);
  const duration = useStudioStore((s) => s.duration);
  const togglePlay = useStudioStore((s) => s.togglePlay);
  const stopVideo = useStudioStore((s) => s.stopVideo);
  const toggleMute = useStudioStore((s) => s.toggleMute);
  const clearMedia = useStudioStore((s) => s.clearMedia);

  return (
    <div
      className="pointer-events-auto absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1 bg-raised px-2 py-1 shadow-lg"
      role="toolbar"
      aria-label="Viewport controls"
    >
      {/* Video Playback Controls */}
      {mediaType === 'video' && (
        <>
          <HUDButton
            label={isPlaying ? 'pause video' : 'play video'}
            onClick={togglePlay}
          >
            {isPlaying ? (
              <Pause size={12} strokeWidth={1.5} className="text-highlight" />
            ) : (
              <Play size={12} strokeWidth={1.5} className="text-highlight" />
            )}
          </HUDButton>
          <HUDButton label="stop video" onClick={stopVideo}>
            <Square size={12} strokeWidth={1.5} />
          </HUDButton>
          <HUDButton
            label={isMuted ? 'unmute audio' : 'mute audio'}
            onClick={toggleMute}
          >
            {isMuted ? (
              <VolumeX size={12} strokeWidth={1.5} className="text-dim" />
            ) : (
              <Volume2 size={12} strokeWidth={1.5} className="text-highlight" />
            )}
          </HUDButton>
          <span className="min-w-16 text-center text-control tabular-nums text-dim">
            {formatTime(playbackTime)} / {formatTime(duration)}
          </span>
          <span aria-hidden className="mx-1 h-4 w-px bg-hairline" />
        </>
      )}

      {/* Viewport Zoom Controls */}
      <HUDButton
        label="zoom out"
        disabled={zoom <= ZOOM_MIN}
        onClick={() => setZoom(zoom / ZOOM_STEP)}
      >
        <Minus size={12} strokeWidth={1.5} />
      </HUDButton>
      <span
        className="min-w-12 text-center text-control tabular-nums text-highlight"
        aria-live="polite"
      >
        {Math.round(zoom * 100)}%
      </span>
      <HUDButton
        label="zoom in"
        disabled={zoom >= ZOOM_MAX}
        onClick={() => setZoom(zoom * ZOOM_STEP)}
      >
        <Plus size={12} strokeWidth={1.5} />
      </HUDButton>
      <HUDButton label="reset pan and zoom" onClick={resetHUD}>
        <span className="text-control">reset</span>
      </HUDButton>

      <span aria-hidden className="mx-1 h-4 w-px bg-hairline" />

      <span className="text-control tabular-nums text-dim">
        {dimensions ? `${dimensions.width}×${dimensions.height}` : 'no media'}
      </span>

      {/* Media Eject / Close Button */}
      {mediaType && (
        <>
          <span aria-hidden className="mx-1 h-4 w-px bg-hairline" />
          <HUDButton label="eject media" onClick={clearMedia}>
            <X size={12} strokeWidth={1.5} />
            <span className="text-control text-dim">eject</span>
          </HUDButton>
        </>
      )}

      <span aria-hidden className="mx-1 h-4 w-px bg-hairline" />

      {/* Theme Toggle */}
      <HUDButton label={`switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} onClick={toggleTheme}>
        {theme === 'dark' ? (
          <Sun size={12} strokeWidth={1.5} />
        ) : (
          <Moon size={12} strokeWidth={1.5} />
        )}
      </HUDButton>
    </div>
  );
}

function HUDButton({
  label,
  onClick,
  disabled = false,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="flex h-6 min-w-6 items-center justify-center gap-1 px-1 text-default transition-colors duration-fast enabled:hover:bg-active enabled:hover:text-highlight disabled:text-dim disabled:opacity-50"
    >
      {children}
    </button>
  );
}
