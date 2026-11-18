import { useEffect } from 'react';
import { useStudioStore } from './store/useStudioStore';
import LeftRail from './components/layout/LeftRail';
import CenterStage from './components/layout/CenterStage';
import RightRail from './components/layout/RightRail';

/**
 * Docked studio shell (D-03): 24px titlebar, three-column workspace
 * (LeftRail 240px / CenterStage flex / RightRail 280px), 24px statusbar.
 * Theme is applied to the document root so token overrides cascade everywhere.
 */
export default function App() {
  const theme = useStudioStore((s) => s.theme);
  const zoom = useStudioStore((s) => s.zoom);
  const dimensions = useStudioStore((s) => s.dimensions);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
    <div className="flex h-full w-full flex-col bg-base text-default">
      <header className="flex h-6 shrink-0 items-center justify-between border-b border-hairline px-2 text-control text-dim">
        <span>rgb://fx / grainrad v1.4.2 [gpu]</span>
        <span>
          untitled studio <span className="text-highlight">● synced</span>
        </span>
        <span>grainrad mono</span>
      </header>

      <div className="flex min-h-0 flex-1">
        <LeftRail />
        <CenterStage />
        <RightRail />
      </div>

      <footer className="flex h-6 shrink-0 items-center justify-between border-t border-hairline px-2 text-control text-dim">
        <span className="tabular-nums">
          zoom {Math.round(zoom * 100)}%
          {dimensions ? ` · ${dimensions.width}×${dimensions.height}` : ''}
        </span>
        <span>profile rec.601 linear</span>
      </footer>
    </div>
  );
}
