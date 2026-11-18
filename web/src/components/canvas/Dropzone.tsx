import { useEffect, useRef } from 'react';
import { Plus } from 'lucide-react';
import { useStudioStore, registerBrowseHandler } from '../../store/useStudioStore';

/** MEDIA-01 accepted inputs: images (PNG, JPG, WebP, GIF) and videos (MP4, WebM). */
const ACCEPT = '.png,.jpg,.jpeg,.webp,.gif,.mp4,.webm,image/*,video/*';

/**
 * Blank-slate standby dropzone (D-04): dashed 1px hairline frame, `+`
 * affordance, mono copy. The hidden file input stays mounted in BOTH states
 * so the LeftRail source buttons can always open the shared browser picker;
 * only the standby card is conditional. CRT scanline texture is allowed in
 * this empty standby state only (DESIGN.md) — as a background, it captures
 * no pointer events.
 */
export default function Dropzone({ dragActive }: { dragActive: boolean }) {
  const loadMediaFile = useStudioStore((s) => s.loadMediaFile);
  const mediaType = useStudioStore((s) => s.mediaType);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    registerBrowseHandler(() => inputRef.current?.click());
    return () => registerBrowseHandler(null);
  }, []);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void loadMediaFile(file);
          e.target.value = ''; // allow re-selecting the same file later
        }}
      />
      {!mediaType && (
        <div
          role="button"
          tabIndex={0}
          aria-label="Load media: drop a file or click to browse"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          className={`pointer-events-auto flex max-w-md cursor-pointer flex-col items-center gap-3 px-10 py-8 text-center transition-colors duration-fast ${
            dragActive
              ? 'border border-solid border-hairline bg-active' // frame steps to solid while dragging (DESIGN.md)
              : 'border border-dashed border-hairline hover:bg-active'
          }`}
          style={{ backgroundImage: 'var(--scanline)' }}
        >
          <Plus size={20} strokeWidth={1} className="text-highlight" aria-hidden />
          <p className="text-default">drop image or video / or browse</p>
          <p className="text-control text-dim">
            png · jpg · webp · gif · mp4 · webm — native dimensions
          </p>
        </div>
      )}
    </>
  );
}
