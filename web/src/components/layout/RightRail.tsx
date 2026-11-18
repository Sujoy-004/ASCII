import type { ReactNode } from 'react';
import { useStudioStore } from '../../store/useStudioStore';
import EffectInspector from '../panels/EffectInspector';
import ToneControls from '../panels/ToneControls';
import ExportDrawer from '../panels/ExportDrawer';

/**
 * Right docked rail (280px) — inspector groups (D-03): dynamic EffectInspector (SHADER-02),
 * pre-tone sliders (SHADER-03), and tabbed ExportDrawer (D-08, MEDIA-03).
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
      <GroupHeader title="effect parameters" state={effect} />
      <div className="px-4 pb-3">
        <EffectInspector />
      </div>

      <GroupHeader title="pre-tone" state="rec.601" />
      <ToneControls />

      <GroupHeader title="export / dispatch" state="client" />
      <ExportDrawer />

      <div className="mt-auto flex justify-end border-t border-hairline p-2">
        <RailButton label="collapse right rail" onClick={toggleRightRail}>
          <span aria-hidden>◨</span>
        </RailButton>
      </div>
    </aside>
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
