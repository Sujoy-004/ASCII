import { useStudioStore } from '../../store/useStudioStore';
import type { RampPreset } from '../../types/studio';

export interface EffectInspectorProps {
  onParamChange?: (key: string, value: number) => void;
}

/**
 * Dynamic parameter inspector panel (D-03, SHADER-02).
 * Displays controls tailored to the active Grainrad effect mode.
 */
export default function EffectInspector({ onParamChange }: EffectInspectorProps) {
  const effect = useStudioStore((s) => s.effect);
  const ascii = useStudioStore((s) => s.ascii);
  const updateAscii = useStudioStore((s) => s.updateAscii);
  const effectParams = useStudioStore((s) => s.effectParams);
  const updateEffectParam = useStudioStore((s) => s.updateEffectParam);

  const handleParam = (key: any, val: number) => {
    updateEffectParam(key, val);
    if (onParamChange) onParamChange(key, val);
  };

  switch (effect) {
    case 'ascii':
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

    case 'dither':
      return (
        <div className="flex flex-col gap-2">
          <SliderRow
            label="color levels"
            value={effectParams.ditherSteps}
            min={2}
            max={16}
            step={1}
            format={(v) => `${v}`}
            onChange={(v) => handleParam('ditherSteps', v)}
          />
          <SliderRow
            label="dither spread"
            value={effectParams.ditherSpread}
            min={0.1}
            max={2.0}
            step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(v) => handleParam('ditherSpread', v)}
          />
        </div>
      );

    case 'halftone':
      return (
        <div className="flex flex-col gap-2">
          <SliderRow
            label="screen frequency"
            value={effectParams.halftoneFreq}
            min={10}
            max={150}
            step={1}
            format={(v) => `${v} lpi`}
            onChange={(v) => handleParam('halftoneFreq', v)}
          />
          <SliderRow
            label="screen angle"
            value={effectParams.halftoneAngle}
            min={-90}
            max={90}
            step={1}
            format={(v) => `${v}°`}
            onChange={(v) => handleParam('halftoneAngle', v)}
          />
          <SliderRow
            label="dot radius"
            value={effectParams.halftoneRadius}
            min={0.2}
            max={2.0}
            step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(v) => handleParam('halftoneRadius', v)}
          />
        </div>
      );

    case 'matrix':
      return (
        <div className="flex flex-col gap-2">
          <SliderRow
            label="fall speed"
            value={effectParams.matrixSpeed}
            min={0.2}
            max={4.0}
            step={0.1}
            format={(v) => `${v.toFixed(1)}x`}
            onChange={(v) => handleParam('matrixSpeed', v)}
          />
          <SliderRow
            label="stream density"
            value={effectParams.matrixDensity}
            min={10}
            max={100}
            step={2}
            format={(v) => `${v}`}
            onChange={(v) => handleParam('matrixDensity', v)}
          />
        </div>
      );

    case 'pixelSort':
      return (
        <div className="flex flex-col gap-2">
          <SliderRow
            label="sort threshold"
            value={effectParams.sortThreshold}
            min={0.05}
            max={0.95}
            step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(v) => handleParam('sortThreshold', v)}
          />
          <SliderRow
            label="streak span"
            value={effectParams.sortSpan}
            min={5}
            max={100}
            step={1}
            format={(v) => `${v} px`}
            onChange={(v) => handleParam('sortSpan', v)}
          />
          <button
            type="button"
            onClick={() =>
              handleParam(
                'sortDirection',
                effectParams.sortDirection === 0 ? 1 : 0
              )
            }
            className="flex h-6 items-center justify-between bg-raised px-2 text-control hover:bg-active"
          >
            <span>direction</span>
            <span className="tabular-nums text-highlight">
              {effectParams.sortDirection === 0 ? '→ horizontal' : '↓ vertical'}
            </span>
          </button>
        </div>
      );

    case 'blockify':
      return (
        <div className="flex flex-col gap-2">
          <SliderRow
            label="block size"
            value={effectParams.genericA}
            min={2}
            max={64}
            step={1}
            format={(v) => `${v} px`}
            onChange={(v) => handleParam('genericA', v)}
          />
          <SliderRow
            label="grid line"
            value={effectParams.genericB}
            min={0}
            max={1}
            step={0.05}
            format={(v) => (v === 0 ? 'off' : v.toFixed(2))}
            onChange={(v) => handleParam('genericB', v)}
          />
        </div>
      );

    case 'dots':
    case 'contour':
    case 'threshold':
    case 'edgeDetect':
    case 'crosshatch':
    case 'waveLines':
    case 'noise':
    case 'voronoi':
      return (
        <div className="flex flex-col gap-2">
          <SliderRow
            label="scale / frequency"
            value={effectParams.genericA}
            min={2}
            max={32}
            step={1}
            format={(v) => `${v}`}
            onChange={(v) => handleParam('genericA', v)}
          />
          <SliderRow
            label="intensity / radius"
            value={effectParams.genericB}
            min={0.1}
            max={3.0}
            step={0.1}
            format={(v) => v.toFixed(1)}
            onChange={(v) => handleParam('genericB', v)}
          />
        </div>
      );

    default:
      return (
        <div className="text-control text-dim py-1">
          Standard tone processing active.
        </div>
      );
  }
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
