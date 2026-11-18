import { useRef } from 'react';
import { useStudioStore } from '../../store/useStudioStore';
import ViewportHUD from '../canvas/ViewportHUD';

/**
 * Center Stage (D-03): canvas viewport with a hardware-accelerated pan/zoom
 * CSS transform layer and the floating ViewportHUD. Pointer drag pans the
 * stage; HUD buttons control zoom and reset.
 */
export default function CenterStage() {
  const zoom = useStudioStore((s) => s.zoom);
  const pan = useStudioStore((s) => s.pan);
  const setPan = useStudioStore((s) => s.setPan);
  const dragRef = useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(
    null,
  );

  return (
    <section
      className="relative min-h-0 min-w-0 flex-1 overflow-hidden bg-base"
      aria-label="Center stage"
    >
      <div
        className="absolute inset-0 flex touch-none items-center justify-center"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          willChange: 'transform',
        }}
        onPointerDown={(e) => {
          dragRef.current = {
            startX: e.clientX,
            startY: e.clientY,
            baseX: pan.x,
            baseY: pan.y,
          };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          const drag = dragRef.current;
          if (!drag) return;
          setPan({
            x: drag.baseX + (e.clientX - drag.startX),
            y: drag.baseY + (e.clientY - drag.startY),
          });
        }}
        onPointerUp={(e) => {
          dragRef.current = null;
          e.currentTarget.releasePointerCapture(e.pointerId);
        }}
        onPointerCancel={() => {
          dragRef.current = null;
        }}
      >
        {/* Media canvas mounts here in plan 02-03 (WebGPU/WebGL engine). */}
        <canvas className="block bg-base" aria-label="Media viewport canvas" />
      </div>

      <ViewportHUD />
    </section>
  );
}
