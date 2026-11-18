import type { ReactNode } from 'react';
import {
  Image as ImageIcon,
  Video,
  Webcam,
  PanelLeftClose,
  PanelRightClose,
  Type as TypeIcon,
  Grid3x3,
  CircleDot,
  Tv,
  Terminal,
  Grip,
  Mountain,
  ArrowDownUp,
  Square,
  Contrast,
  Spline,
  Hash,
  Waves,
  CloudFog,
  Network,
  Palette,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import type { EffectMode, MediaType } from '../../types/studio';

const EFFECT_LIST: { mode: EffectMode; label: string; Icon: typeof TypeIcon }[] = [
  { mode: 'ascii', label: 'ascii', Icon: TypeIcon },
  { mode: 'dither', label: 'dither', Icon: Grid3x3 },
  { mode: 'halftone', label: 'halftone', Icon: CircleDot },
  { mode: 'vhs', label: 'vhs', Icon: Tv },
  { mode: 'matrix', label: 'matrix', Icon: Terminal },
  { mode: 'dots', label: 'dots', Icon: Grip },
  { mode: 'contour', label: 'contour', Icon: Mountain },
  { mode: 'pixelSort', label: 'pixel sort', Icon: ArrowDownUp },
  { mode: 'blockify', label: 'blockify', Icon: Square },
  { mode: 'threshold', label: 'threshold', Icon: Contrast },
  { mode: 'edgeDetect', label: 'edge detect', Icon: Spline },
  { mode: 'crosshatch', label: 'crosshatch', Icon: Hash },
  { mode: 'waveLines', label: 'wave lines', Icon: Waves },
  { mode: 'noise', label: 'noise', Icon: CloudFog },
  { mode: 'voronoi', label: 'voronoi', Icon: Network },
  { mode: 'tone', label: 'tone', Icon: Palette },
];

const PRESETS: { preset: 'standard' | 'dense' | 'simple' | 'blocks'; label: string; tag: string }[] = [
  { preset: 'standard', label: 'standard', tag: 'p01' },
  { preset: 'dense', label: 'dense', tag: 'p02' },
  { preset: 'simple', label: 'simple', tag: 'p03' },
  { preset: 'blocks', label: 'blocks', tag: 'p04' },
];

const SOURCES: { type: MediaType; label: string; Icon: typeof ImageIcon }[] = [
  { type: 'image', label: 'image', Icon: ImageIcon },
  { type: 'video', label: 'video', Icon: Video },
  { type: 'webcam', label: 'webcam', Icon: Webcam },
];

/**
 * Left docked rail (240px) — media source, 16 Grainrad effect tiles, macro
 * presets (D-03). Collapses to a 48px icon dock.
 */
export default function LeftRail() {
  const effect = useStudioStore((s) => s.effect);
  const setEffect = useStudioStore((s) => s.setEffect);
  const ascii = useStudioStore((s) => s.ascii);
  const updateAscii = useStudioStore((s) => s.updateAscii);
  const mediaType = useStudioStore((s) => s.mediaType);
  const dimensions = useStudioStore((s) => s.dimensions);
  const leftCollapsed = useStudioStore((s) => s.leftCollapsed);
  const toggleLeftRail = useStudioStore((s) => s.toggleLeftRail);
  const toggleRightRail = useStudioStore((s) => s.toggleRightRail);
  const startWebcam = useStudioStore((s) => s.startWebcam);
  const stopWebcam = useStudioStore((s) => s.stopWebcam);
  const openFileBrowser = useStudioStore((s) => s.openFileBrowser);

  if (leftCollapsed) {
    return (
      <aside
        className="flex w-12 shrink-0 flex-col items-center gap-1 border-r border-hairline bg-base py-2"
        aria-label="Left rail (collapsed)"
      >
        <RailButton label="expand left rail" onClick={toggleLeftRail}>
          <span aria-hidden>◧</span>
        </RailButton>
        {EFFECT_LIST.map(({ mode, Icon }) => (
          <RailButton
            key={mode}
            label={`effect: ${mode}`}
            active={effect === mode}
            onClick={() => setEffect(mode)}
          >
            <Icon size={16} strokeWidth={1.5} />
          </RailButton>
        ))}
        <div className="mt-auto">
          <RailButton label="toggle right rail" onClick={toggleRightRail}>
            <PanelRightClose size={16} strokeWidth={1.5} />
          </RailButton>
        </div>
      </aside>
    );
  }

  return (
    <aside
      className="flex w-60 shrink-0 flex-col overflow-y-auto border-r border-hairline bg-base"
      aria-label="Left rail"
    >
      <SectionHeader title="source input" state={mediaType ?? 'standby'} />
      <div className="px-4 pb-3">
        <div className="flex gap-1">
          {SOURCES.map(({ type, label, Icon }) => (
            <SourceButton
              key={type}
              type={type}
              label={label}
              Icon={Icon}
              onSelect={() => {
                if (type === 'webcam') {
                  // MEDIA-02: webcam source toggles the live feed on/off.
                  if (mediaType === 'webcam') stopWebcam();
                  else void startWebcam();
                } else {
                  // image/video sources open the shared file picker.
                  openFileBrowser();
                }
              }}
            />
          ))}
        </div>
        <div className="mt-2 flex items-center justify-between text-dim text-control">
          <span>dimensions</span>
          <span className="tabular-nums text-highlight">
            {dimensions ? `${dimensions.width}x${dimensions.height}` : '—'}
          </span>
        </div>
      </div>

      <SectionHeader title="pipeline mode" state={`${EFFECT_LIST.length}`} />
      <div className="grid grid-cols-2 gap-px bg-hairline" role="radiogroup" aria-label="Effect mode">
        {EFFECT_LIST.map(({ mode, label, Icon }) => {
          const active = effect === mode;
          return (
            <button
              key={mode}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => setEffect(mode)}
              className={`flex h-6 items-center gap-2 px-2 text-control transition-colors duration-fast ${
                active ? 'bg-active text-highlight' : 'bg-base text-default hover:bg-active'
              }`}
            >
              <span aria-hidden className="w-3 text-center">{active ? '●' : '○'}</span>
              <span className="truncate">{label}</span>
              <Icon size={12} strokeWidth={1.5} className="ml-auto shrink-0" />
            </button>
          );
        })}
      </div>

      <SectionHeader title="macro presets" state={`${PRESETS.length}`} />
      <div className="flex flex-wrap gap-1 px-4 pb-3">
        {PRESETS.map(({ preset, label, tag }) => (
          <button
            key={preset}
            type="button"
            onClick={() => updateAscii({ rampPreset: preset, customChars: '' })}
            aria-pressed={ascii.rampPreset === preset && ascii.customChars === ''}
            className={`flex h-6 items-center gap-2 px-2 text-control transition-colors duration-fast ${
              ascii.rampPreset === preset && ascii.customChars === ''
                ? 'bg-active text-highlight'
                : 'bg-raised text-default hover:bg-active'
            }`}
          >
            <span>{label}</span>
            <span className="text-dim">{tag}</span>
          </button>
        ))}
      </div>

      <div className="mt-auto flex justify-between border-t border-hairline p-2">
        <RailButton label="collapse left rail" onClick={toggleLeftRail}>
          <PanelLeftClose size={16} strokeWidth={1.5} />
        </RailButton>
        <RailButton label="toggle right rail" onClick={toggleRightRail}>
          <PanelRightClose size={16} strokeWidth={1.5} />
        </RailButton>
      </div>
    </aside>
  );
}

function SectionHeader({ title, state }: { title: string; state: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-2 text-control text-dim">
      <span aria-hidden>− {title}</span>
      <span className="tabular-nums">{state}</span>
    </div>
  );
}

function SourceButton({
  type,
  label,
  Icon,
  onSelect,
}: {
  type: MediaType;
  label: string;
  Icon: typeof ImageIcon;
  onSelect: () => void;
}) {
  const mediaType = useStudioStore((s) => s.mediaType);
  return (
    <button
      type="button"
      data-source={type}
      aria-pressed={mediaType === type}
      title={
        type === 'webcam'
          ? mediaType === 'webcam'
            ? 'stop webcam'
            : 'start webcam'
          : `browse ${label} file`
      }
      onClick={onSelect}
      className={`flex h-6 flex-1 items-center justify-center gap-1 text-control transition-colors duration-fast ${
        mediaType === type ? 'bg-active text-highlight' : 'bg-raised text-default hover:bg-active'
      }`}
    >
      <Icon size={12} strokeWidth={1.5} />
      <span>{label}</span>
    </button>
  );
}

function RailButton({
  label,
  active = false,
  onClick,
  children,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={`flex h-6 w-8 items-center justify-center transition-colors duration-fast ${
        active ? 'bg-active text-highlight' : 'text-dim hover:bg-active hover:text-highlight'
      }`}
    >
      {children}
    </button>
  );
}
