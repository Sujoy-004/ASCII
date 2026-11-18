import { useStudioStore } from '../../store/useStudioStore';

/**
 * Pre-tone sliders panel (SHADER-03).
 * Provides sliders for Brightness, Contrast, Saturation, Hue Rotation, Gamma, and Invert toggle switch.
 */
export default function ToneControls() {
  const tone = useStudioStore((s) => s.tone);
  const updateTone = useStudioStore((s) => s.updateTone);
  const resetTone = useStudioStore((s) => s.resetTone);

  return (
    <div className="flex flex-col gap-2 px-4 pb-3">
      <SliderRow
        label="brightness"
        value={tone.brightness}
        min={0}
        max={2}
        step={0.01}
        format={(v) => v.toFixed(2)}
        onChange={(brightness) => updateTone({ brightness })}
      />
      <SliderRow
        label="contrast"
        value={tone.contrast}
        min={0}
        max={2}
        step={0.01}
        format={(v) => v.toFixed(2)}
        onChange={(contrast) => updateTone({ contrast })}
      />
      <SliderRow
        label="saturation"
        value={tone.saturation}
        min={0}
        max={2}
        step={0.01}
        format={(v) => v.toFixed(2)}
        onChange={(saturation) => updateTone({ saturation })}
      />
      <SliderRow
        label="hue rotation"
        value={tone.hueRotation}
        min={-180}
        max={180}
        step={1}
        format={(v) => `${v}°`}
        onChange={(hueRotation) => updateTone({ hueRotation })}
      />
      <SliderRow
        label="gamma"
        value={tone.gamma}
        min={0.1}
        max={3}
        step={0.01}
        format={(v) => v.toFixed(2)}
        onChange={(gamma) => updateTone({ gamma })}
      />
      <button
        type="button"
        onClick={() => updateTone({ invert: !tone.invert })}
        className="flex h-6 items-center justify-between text-control hover:bg-active"
      >
        <span>invert</span>
        <span className="tabular-nums text-highlight">{tone.invert ? '● on' : '○ off'}</span>
      </button>
      <button
        type="button"
        onClick={resetTone}
        className="h-6 bg-raised text-left text-control hover:bg-active px-2"
      >
        reset tone
      </button>
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
