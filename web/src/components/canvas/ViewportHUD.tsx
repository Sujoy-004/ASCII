import type { ReactNode } from 'react';
import { Minus, Plus, Sun, Moon } from 'lucide-react';
import { useStudioStore, ZOOM_MAX, ZOOM_MIN } from '../../store/useStudioStore';

const ZOOM_STEP = 1.25;

/**
 * Floating viewport HUD pinned bottom-center of Center Stage (STUDIO-03):
 * [-] [100%] [+] [Reset], native media dimensions, dark/light theme toggle.
 */
export default function ViewportHUD() {
  const zoom = useStudioStore((s) => s.zoom);
  const setZoom = useStudioStore((s) => s.setZoom);
  const resetHUD = useStudioStore((s) => s.resetHUD);
  const dimensions = useStudioStore((s) => s.dimensions);
  const theme = useStudioStore((s) => s.theme);
  const toggleTheme = useStudioStore((s) => s.toggleTheme);

  return (
    <div
      className="pointer-events-auto absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1 bg-raised px-2 py-1"
      role="toolbar"
      aria-label="Viewport controls"
    >
      <HUDButton
        label="zoom out"
        disabled={zoom <= ZOOM_MIN}
        onClick={() => setZoom(zoom / ZOOM_STEP)}
      >
        <Minus size={12} strokeWidth={1.5} />
      </HUDButton>
      <span
        className="min-w-14 text-center text-control tabular-nums text-highlight"
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

      <span aria-hidden className="mx-1 h-4 w-px bg-hairline" />

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
