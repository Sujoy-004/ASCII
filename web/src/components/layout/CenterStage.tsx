import { useEffect, useRef, useState } from 'react';
import type { DragEvent as ReactDragEvent, PointerEvent as ReactPointerEvent } from 'react';
import * as THREE from 'three/webgpu';
import { useStudioStore, registerVideoElement } from '../../store/useStudioStore';
import { StudioPipeline } from '../../engine/Pipeline';
import ViewportHUD from '../canvas/ViewportHUD';
import Dropzone from '../canvas/Dropzone';

/**
 * Center Stage (D-03): canvas viewport with a hardware-accelerated pan/zoom
 * CSS transform layer, Three.js WebGPU / WebGL2 shader pipeline, and ViewportHUD.
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
  const dimensions = useStudioStore((s) => s.dimensions);
  const loadMediaFile = useStudioStore((s) => s.loadMediaFile);
  const setDimensions = useStudioStore((s) => s.setDimensions);
  const tone = useStudioStore((s) => s.tone);
  const ascii = useStudioStore((s) => s.ascii);
  const effect = useStudioStore((s) => s.effect);
  const effectParams = useStudioStore((s) => s.effectParams);
  const setIsPlaying = useStudioStore((s) => s.setIsPlaying);
  const setPlaybackTime = useStudioStore((s) => s.setPlaybackTime);
  const setDuration = useStudioStore((s) => s.setDuration);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pipelineRef = useRef<StudioPipeline | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const dragRef = useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(
    null,
  );
  const [dragOver, setDragOver] = useState(false);
  const webcamActive = mediaType === 'webcam';

  // 1. Initialize Pipeline on mount
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const pipeline = new StudioPipeline({ canvas });
    pipelineRef.current = pipeline;

    let animId: number;
    const startTime = performance.now();

    const loop = (time: number) => {
      pipeline.render((time - startTime) * 0.001);
      animId = requestAnimationFrame(loop);
    };

    pipeline.init().then(() => {
      pipeline.resize(canvas.clientWidth || 800, canvas.clientHeight || 600);
      animId = requestAnimationFrame(loop);
    }).catch((err) => {
      console.warn('Studio shader pipeline init warning:', err);
    });

    return () => {
      cancelAnimationFrame(animId);
      pipeline.dispose();
      pipelineRef.current = null;
    };
  }, []);

  // 2. Synchronize tone and ascii settings to pipeline
  useEffect(() => {
    if (pipelineRef.current) {
      pipelineRef.current.updateTone(tone);
    }
  }, [tone]);

  useEffect(() => {
    if (pipelineRef.current) {
      pipelineRef.current.updateAscii(ascii);
    }
  }, [ascii]);

  useEffect(() => {
    if (pipelineRef.current) {
      pipelineRef.current.setEffect(effect);
    }
  }, [effect]);

  useEffect(() => {
    if (pipelineRef.current) {
      for (const [key, value] of Object.entries(effectParams)) {
        pipelineRef.current.updateEffectParam(key, value);
      }
    }
  }, [effectParams]);

  // 3. Synchronize media texture to pipeline
  useEffect(() => {
    const pipeline = pipelineRef.current;
    if (!pipeline) return;

    if (mediaType === 'image' && mediaUrl && dimensions) {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        const tex = new THREE.Texture(img);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.needsUpdate = true;
        pipeline.setSourceTexture(tex);
        pipeline.resize(dimensions.width, dimensions.height);
      };
      img.src = mediaUrl;
    } else if ((mediaType === 'video' || webcamActive) && videoRef.current) {
      const tex = new THREE.VideoTexture(videoRef.current);
      tex.colorSpace = THREE.SRGBColorSpace;
      pipeline.setSourceTexture(tex);
      const w = dimensions?.width || videoRef.current.videoWidth || 800;
      const h = dimensions?.height || videoRef.current.videoHeight || 600;
      pipeline.resize(w, h);
    } else if (!mediaType) {
      pipeline.clearSource();
    }
  }, [mediaType, mediaUrl, dimensions, webcamActive]);

  // Register persistent video element on mount
  useEffect(() => {
    if (videoRef.current) {
      registerVideoElement(videoRef.current);
    }
    return () => {
      registerVideoElement(null);
    };
  }, []);

  const onDragOver = (e: ReactDragEvent<HTMLElement>) => {
    e.preventDefault();
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
    // Only capture pointer on the background stage itself, not when clicking dropzone
    const target = e.target as HTMLElement;
    if (target.closest('[role="button"]') || target.closest('button')) {
      return;
    }

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
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // ignore
    }
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
      {/* Hidden file input always available on stage */}
      <Dropzone dragActive={dragOver} />

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
        {/* WebGPU / WebGL2 Engine Canvas */}
        <canvas
          ref={canvasRef}
          className="block bg-base"
          style={{
            width: dimensions ? `${dimensions.width}px` : '800px',
            height: dimensions ? `${dimensions.height}px` : '600px',
          }}
          aria-label="Media viewport canvas"
        />

        {/* Single persistent off-screen video playback element for video and live webcam */}
        <video
          ref={videoRef}
          playsInline
          preload="auto"
          loop={mediaType === 'video'}
          style={{
            position: 'fixed',
            top: '-9999px',
            left: '-9999px',
            width: '320px',
            height: '240px',
            opacity: 0,
            pointerEvents: 'none',
          }}
          onLoadedMetadata={(e) => {
            const el = e.currentTarget;
            if (el.videoWidth && el.videoHeight) {
              setDimensions({ width: el.videoWidth, height: el.videoHeight });
              if (pipelineRef.current) {
                pipelineRef.current.resize(el.videoWidth, el.videoHeight);
              }
            }
            if (el.duration && !isNaN(el.duration)) {
              setDuration(el.duration);
            }
          }}
          onPlaying={(e) => {
            const el = e.currentTarget;
            if (el.videoWidth && el.videoHeight) {
              const cur = useStudioStore.getState().dimensions;
              if (!cur || cur.width !== el.videoWidth || cur.height !== el.videoHeight) {
                setDimensions({ width: el.videoWidth, height: el.videoHeight });
                if (pipelineRef.current) {
                  pipelineRef.current.resize(el.videoWidth, el.videoHeight);
                }
              }
            }
            setIsPlaying(true);
          }}
          onTimeUpdate={(e) => {
            setPlaybackTime(e.currentTarget.currentTime || 0);
          }}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
        />
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
