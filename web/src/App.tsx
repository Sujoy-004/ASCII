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
  const setLeftCollapsed = useStudioStore((s) => s.setLeftCollapsed);
  const setRightCollapsed = useStudioStore((s) => s.setRightCollapsed);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768) {
        setLeftCollapsed(true);
        setRightCollapsed(true);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [setLeftCollapsed, setRightCollapsed]);

  return (
    <div className="flex h-full w-full flex-col bg-base text-default">
      <header
        className="flex h-6 shrink-0 items-center justify-between border-b border-hairline px-2 text-control text-dim select-none"
        role="banner"
      >
        <a
          href="/"
          title="Return to Product Overview"
          className="truncate text-dim hover:text-highlight transition-colors"
        >
          rgb-ascii studio v0.1.0 [webgpu]
        </a>
        <span className="hidden sm:inline">
          local session <span className="text-highlight">● offline-ready</span>
        </span>
        <span className="tabular-nums">ascii studio</span>
      </header>

      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        <LeftRail />
        <CenterStage />
        <RightRail />
      </div>

      <footer
        className="flex h-6 shrink-0 items-center justify-between border-t border-hairline px-2 text-control text-dim select-none"
        role="contentinfo"
      >
        <span className="tabular-nums truncate">
          zoom {Math.round(zoom * 100)}%
          {dimensions ? ` · ${dimensions.width}×${dimensions.height}` : ''}
        </span>
        <span className="truncate">rec.601 linear</span>
      </footer>
    </div>
  );
}
