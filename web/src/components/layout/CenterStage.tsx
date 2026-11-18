import { useEffect, useRef, useState } from 'react';
import type { DragEvent as ReactDragEvent, PointerEvent as ReactPointerEvent } from 'react';
import { useStudioStore, registerVideoElement } from '../../store/useStudioStore';
import ViewportHUD from '../canvas/ViewportHUD';
import Dropzone from '../canvas/Dropzone';

/**
 * Center Stage (D-03): canvas viewport with a hardware-accelerated pan/zoom
 * CSS transform layer and the floating ViewportHUD. Pointer drag pans the
 * stage; HUD buttons control zoom and reset. Media renders at its NATIVE
 * uncapped pixel size (max-w-none overrides Tailwind preflight downscaling);
 * the zoom HUD exists to navigate it.
 *
 * Stage-wide drag-and-drop (D-04, MEDIA-01): dropping a file anywhere over
 * the stage loads it; the standby dropzone card shows while no media is
 * loaded and its frame steps to solid hairline while dragging.
 */
export default function CenterStage() {
  const zoom = useStudioStore((s) => s.zoom);
  const pan = useStudioStore((s) => s.pan);
  const setPan = useStudioStore((s) => s.setPan);
  const mediaType = useStudioStore((s) => s.mediaType);
  const mediaUrl = useStudioStore((s) => s.mediaUrl);
  const mediaName = useStudioStore((s) => s.mediaName);
  const dimensions = useStudioStore((s) => s.dimensions);
  const loadMediaFile = useStudioStore((s) => s.loadMediaFile);
  const setDimensions = useStudioStore((s) => s.setDimensions);

  const dragRef = useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(
    null,
  );
  const [dragOver, setDragOver] = useState(false);
  const webcamActive = mediaType === 'webcam';
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // MEDIA-02: register the live webcam <video> with the store so
  // startWebcam() can attach the MediaStream (and detach on unmount).
  // T-02-04: if this stage unmounts while the feed is live, stop the tracks
  // immediately — the camera indicator must never stay lit. In every other
  // path (stop button, media replacement) the stream is already null and
  // this is a no-op.
  useEffect(() => {
    registerVideoElement(videoRef.current);
    return () => {
      registerVideoElement(null);
      useStudioStore.getState().stopWebcam();
    };
  }, [webcamActive]);

  const onDragOver = (e: ReactDragEvent<HTMLElement>) => {
    e.preventDefault(); // required to allow drop
    setDragOver(true);
  };

  const onDragLeave = (e: ReactDragEvent<HTMLElement>) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragOver(false);
  };

  const onDrop = (e: ReactDragEvent<HTMLElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void loadMediaFile(file);
  };

  const onPointerDown = (e: ReactPointerEvent<HTMLElement>) => {
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      baseX: pan.x,
      baseY: pan.y,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: ReactPointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    setPan({
      x: drag.baseX + (e.clientX - drag.startX),
      y: drag.baseY + (e.clientY - drag.startY),
    });
  };

  const onPointerUp = (e: ReactPointerEvent<HTMLElement>) => {
    dragRef.current = null;
    e.currentTarget.releasePointerCapture(e.pointerId);
  };

  const onPointerCancel = () => {
    dragRef.current = null;
  };

  return (
    <section
      className="relative min-h-0 min-w-0 flex-1 overflow-hidden bg-base"
      aria-label="Center stage"
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <div
        className="absolute inset-0 flex touch-none items-center justify-center"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          willChange: 'transform',
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
      >
        {/* WebGPU/WebGL engine canvas mounts here in plan 02-03. */}
        {mediaType === null && <canvas className="block bg-base" aria-label="Media viewport canvas" />}

        {mediaType === 'image' && mediaUrl && dimensions && (
          <img
            src={mediaUrl}
            alt={mediaName ?? 'loaded image'}
            width={dimensions.width}
            height={dimensions.height}
            draggable={false}
            className="block max-w-none select-none"
            style={{ width: dimensions.width, height: dimensions.height }}
          />
        )}

        {mediaType === 'video' && mediaUrl && dimensions && (
          <video
            src={mediaUrl}
            controls
            loop
            autoPlay
            className="block max-w-none"
            style={{ width: dimensions.width, height: dimensions.height }}
          />
        )}

        {webcamActive && (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="block max-w-none"
            onLoadedMetadata={(e) => {
              const el = e.currentTarget;
              if (el.videoWidth && el.videoHeight) {
                setDimensions({ width: el.videoWidth, height: el.videoHeight });
              }
            }}
          />
        )}

        <Dropzone dragActive={dragOver} />
      </div>

      {dragOver && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{ background: 'var(--overlay-drag)' }}
        />
      )}

      <ViewportHUD />
    </section>
  );
}
