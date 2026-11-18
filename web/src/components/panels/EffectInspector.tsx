import { useState } from 'react';
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

  // Local state for interactive effect sliders
  const [ditherSteps, setDitherSteps] = useState(4);
  const [ditherSpread, setDitherSpread] = useState(0.5);

  const [halftoneFreq, setHalftoneFreq] = useState(50);
  const [halftoneAngle, setHalftoneAngle] = useState(45);
  const [halftoneRadius, setHalftoneRadius] = useState(1.0);

  const [matrixSpeed, setMatrixSpeed] = useState(1.0);
  const [matrixDensity, setMatrixDensity] = useState(40);

  const [sortThreshold, setSortThreshold] = useState(0.5);
  const [sortSpan, setSortSpan] = useState(20);

  const [paramA, setParamA] = useState(8);
  const [paramB, setParamB] = useState(1);

  const handleParam = (key: string, val: number) => {
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
            value={ditherSteps}
            min={2}
            max={16}
            step={1}
            format={(v) => `${v}`}
            onChange={(v) => { setDitherSteps(v); handleParam('ditherSteps', v); }}
          />
          <SliderRow
            label="dither spread"
            value={ditherSpread}
            min={0.1}
            max={2.0}
            step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(v) => { setDitherSpread(v); handleParam('ditherSpread', v); }}
          />
        </div>
      );

    case 'halftone':
      return (
        <div className="flex flex-col gap-2">
          <SliderRow
            label="screen frequency"
            value={halftoneFreq}
            min={10}
            max={150}
            step={1}
            format={(v) => `${v} lpi`}
            onChange={(v) => { setHalftoneFreq(v); handleParam('halftoneFreq', v); }}
          />
          <SliderRow
            label="screen angle"
            value={halftoneAngle}
            min={-90}
            max={90}
            step={1}
            format={(v) => `${v}°`}
            onChange={(v) => { setHalftoneAngle(v); handleParam('halftoneAngle', v); }}
          />
          <SliderRow
            label="dot radius"
            value={halftoneRadius}
            min={0.2}
            max={2.0}
            step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(v) => { setHalftoneRadius(v); handleParam('halftoneRadius', v); }}
          />
        </div>
      );

    case 'matrix':
      return (
        <div className="flex flex-col gap-2">
          <SliderRow
            label="fall speed"
            value={matrixSpeed}
            min={0.2}
            max={4.0}
            step={0.1}
            format={(v) => `${v.toFixed(1)}x`}
            onChange={(v) => { setMatrixSpeed(v); handleParam('matrixSpeed', v); }}
          />
          <SliderRow
            label="stream density"
            value={matrixDensity}
            min={10}
            max={100}
            step={2}
            format={(v) => `${v}`}
            onChange={(v) => { setMatrixDensity(v); handleParam('matrixDensity', v); }}
          />
        </div>
      );

    case 'pixelSort':
      return (
        <div className="flex flex-col gap-2">
          <SliderRow
            label="sort threshold"
            value={sortThreshold}
            min={0.1}
            max={0.9}
            step={0.05}
            format={(v) => v.toFixed(2)}
            onChange={(v) => { setSortThreshold(v); handleParam('sortThreshold', v); }}
          />
          <SliderRow
            label="streak span"
            value={sortSpan}
            min={5}
            max={60}
            step={1}
            format={(v) => `${v} px`}
            onChange={(v) => { setSortSpan(v); handleParam('sortSpan', v); }}
          />
        </div>
      );

    case 'dots':
    case 'contour':
    case 'blockify':
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
            value={paramA}
            min={2}
            max={32}
            step={1}
            format={(v) => `${v}`}
            onChange={(v) => { setParamA(v); handleParam('genericA', v); }}
          />
          <SliderRow
            label="intensity / radius"
            value={paramB}
            min={0.1}
            max={3.0}
            step={0.1}
            format={(v) => v.toFixed(1)}
            onChange={(v) => { setParamB(v); handleParam('genericB', v); }}
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
