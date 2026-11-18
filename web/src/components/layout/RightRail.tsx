import type { ReactNode } from 'react';
import { useStudioStore } from '../../store/useStudioStore';
import type { RampPreset } from '../../types/studio';
import ToneControls from '../panels/ToneControls';

/**
 * Right docked rail (280px) — inspector groups (D-03): parameter inspector,
 * pre-tone sliders (SHADER-03), export drawer container. Collapses to a
 * 48px icon dock. Export actions wire in plan 02-05; per-effect uniform
 * panels wire in plan 02-04.
 */
export default function RightRail() {
  const rightCollapsed = useStudioStore((s) => s.rightCollapsed);
  const toggleRightRail = useStudioStore((s) => s.toggleRightRail);
  const toggleLeftRail = useStudioStore((s) => s.toggleLeftRail);
  const effect = useStudioStore((s) => s.effect);

  if (rightCollapsed) {
    return (
      <aside
        className="flex w-12 shrink-0 flex-col items-center gap-1 border-l border-hairline bg-base py-2"
        aria-label="Right rail (collapsed)"
      >
        <RailButton label="expand right rail" onClick={toggleRightRail}>
          <span aria-hidden>◨</span>
        </RailButton>
        <RailButton label="toggle left rail" onClick={toggleLeftRail}>
          <span aria-hidden>◧</span>
        </RailButton>
        <span className="mt-8 -rotate-90 text-control text-dim whitespace-nowrap">
          inspector · {effect}
        </span>
      </aside>
    );
  }

  return (
    <aside
      className="flex w-72 shrink-0 flex-col overflow-y-auto border-l border-hairline bg-base"
      aria-label="Right rail"
    >
      <GroupHeader title="inspector" state={effect} />
      <div className="px-4 pb-3">
        <AsciiParams />
      </div>

      <GroupHeader title="pre-tone" state="rec.601" />
      <ToneControls />

      <GroupHeader title="export / dispatch" state="— " />
      <ExportDrawer />

      <div className="mt-auto flex justify-end border-t border-hairline p-2">
        <RailButton label="collapse right rail" onClick={toggleRightRail}>
          <span aria-hidden>◨</span>
        </RailButton>
      </div>
    </aside>
  );
}

/** ASCII engine params (SHADER-01) — fully wired to the store. */
function AsciiParams() {
  const ascii = useStudioStore((s) => s.ascii);
  const updateAscii = useStudioStore((s) => s.updateAscii);

  return (
    <div className="flex flex-col gap-2">
      <SliderRow
        label="cell size"
        value={ascii.cellScale}
        min={4}
        max={32}
        step={1}
        format={(v) => `${v} px`}
        onChange={(cellScale) => updateAscii({ cellScale })}
      />
      <SliderRow
        label="char spacing"
        value={ascii.charSpacing}
        min={0}
        max={8}
        step={0.5}
        format={(v) => `${v} px`}
        onChange={(charSpacing) => updateAscii({ charSpacing })}
      />
      <SliderRow
        label="cell aspect"
        value={ascii.charAspect}
        min={0.25}
        max={1}
        step={0.05}
        format={(v) => v.toFixed(2)}
        onChange={(charAspect) => updateAscii({ charAspect })}
      />
      <label className="flex h-6 items-center justify-between text-control">
        <span>glyph ramp</span>
        <select
          value={ascii.rampPreset}
          onChange={(e) => updateAscii({ rampPreset: e.target.value as RampPreset, customChars: '' })}
          className="h-6 bg-raised px-2 text-control text-highlight hover:bg-active focus-visible:bg-active"
        >
          <option value="standard">standard</option>
          <option value="dense">dense</option>
          <option value="simple">simple</option>
          <option value="blocks">blocks</option>
        </select>
      </label>
      <label className="flex h-6 items-center justify-between gap-2 text-control">
        <span className="shrink-0">custom ramp</span>
        <input
          type="text"
          value={ascii.customChars}
          placeholder="(uses preset)"
          onChange={(e) => updateAscii({ customChars: e.target.value })}
          className="h-6 w-40 bg-raised px-2 text-control text-highlight placeholder:text-dim hover:bg-active focus-visible:bg-active"
        />
      </label>
    </div>
  );
}

/**
 * Export drawer container (D-08). Buttons render per the approved design but
 * are disabled until plan 02-05 wires the export engine — no dead handlers.
 */
function ExportDrawer() {
  return (
    <div className="flex flex-col gap-1 px-4 pb-3">
      <button
        type="button"
        disabled
        className="flex h-6 items-center justify-between bg-raised px-2 text-control text-dim"
        title="Export engine lands in plan 02-05"
      >
        <span>export png frame</span>
        <span className="tabular-nums">native</span>
      </button>
      <div className="grid grid-cols-2 gap-1">
        {(['jpeg', 'svg', 'txt', 'gif'] as const).map((format) => (
          <button
            key={format}
            type="button"
            disabled
            className="h-6 bg-raised text-left px-2 text-control text-dim"
            title="Export engine lands in plan 02-05"
          >
            {format}
          </button>
        ))}
      </div>
    </div>
  );
}

function GroupHeader({ title, state, children }: { title: string; state: string; children?: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-t border-hairline px-4 py-2 text-control text-dim first:border-t-0">
      <span aria-hidden>− {title}</span>
      {children ?? <span className="tabular-nums">{state}</span>}
    </div>
  );
}

/** Slider: 1px hairline track, square thumb, label left / tabular value right. */
function SliderRow({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <div className="flex h-4 items-center justify-between text-control">
        <span>{label}</span>
        <span className="tabular-nums text-highlight">{format(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={label}
        data-slider="true"
        className="h-4 w-full cursor-ew-resize appearance-none bg-transparent"
      />
    </div>
  );
}

function RailButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="flex h-6 w-8 items-center justify-center text-dim transition-colors duration-fast hover:bg-active hover:text-highlight"
    >
      {children}
    </button>
  );
}
