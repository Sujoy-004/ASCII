import { useStudioStore } from './store/useStudioStore';

/**
 * Root shell. Plan task 1 (tracer): proves end-to-end canvas rendering and
 * store binding — a responsive canvas container receiving pan/zoom transform
 * updates from the Zustand store. The full three-column layout composes in
 * task 2.
 */
export default function App() {
  const theme = useStudioStore((s) => s.theme);
  const zoom = useStudioStore((s) => s.zoom);
  const pan = useStudioStore((s) => s.pan);

  return (
    <div
      data-theme={theme}
      className="flex h-full w-full flex-col bg-base text-default"
    >
      <main
        className="relative min-h-0 flex-1 overflow-hidden bg-base"
        aria-label="Canvas stage"
      >
        {/* Pan/zoom CSS transform layer (hardware-accelerated per research). */}
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
            willChange: 'transform',
          }}
        >
          <canvas
            className="block h-full w-full bg-base"
            aria-label="Media viewport canvas"
          />
        </div>
      </main>
    </div>
  );
}
