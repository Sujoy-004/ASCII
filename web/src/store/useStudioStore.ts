import { create } from 'zustand';
import type {
  AsciiSettings,
  Dimensions,
  EffectMode,
  MediaType,
  ThemeMode,
  ToneSettings,
} from '../types/studio';

interface Pan {
  x: number;
  y: number;
}

interface MediaState {
  mediaType: MediaType | null;
  mediaUrl: string | null;
  mediaName: string | null;
  dimensions: Dimensions | null;
}

interface StudioState extends MediaState {
  // Viewport HUD (STUDIO-03)
  zoom: number;
  pan: Pan;
  setZoom: (zoom: number) => void;
  setPan: (pan: Pan) => void;
  resetHUD: () => void;

  // Active effect selection (D-02)
  effect: EffectMode;
  setEffect: (effect: EffectMode) => void;

  // Pre-tone adjustments (SHADER-03)
  tone: ToneSettings;
  updateTone: (patch: Partial<ToneSettings>) => void;
  resetTone: () => void;

  // ASCII engine parameters (SHADER-01)
  ascii: AsciiSettings;
  updateAscii: (patch: Partial<AsciiSettings>) => void;

  // Theme (STUDIO-03)
  theme: ThemeMode;
  toggleTheme: () => void;

  // Sidebar collapse (D-03)
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  toggleLeftRail: () => void;
  toggleRightRail: () => void;

  // Media state setters (media ingestion actions land in plan task 3)
  setMedia: (media: Partial<MediaState>) => void;
  setDimensions: (dimensions: Dimensions) => void;
}

export const DEFAULT_TONE: ToneSettings = {
  brightness: 1,
  contrast: 1,
  saturation: 1,
  hueRotation: 0,
  gamma: 1,
  invert: false,
};

export const DEFAULT_ASCII: AsciiSettings = {
  cellScale: 8,
  charSpacing: 0,
  charAspect: 0.5,
  rampPreset: 'standard',
  customChars: '',
};

const DEFAULT_PAN: Pan = { x: 0, y: 0 };
const DEFAULT_ZOOM = 1;

export const useStudioStore = create<StudioState>()((set) => ({
  mediaType: null,
  mediaUrl: null,
  mediaName: null,
  dimensions: null,

  zoom: DEFAULT_ZOOM,
  pan: DEFAULT_PAN,
  setZoom: (zoom) => set({ zoom: clampZoom(zoom) }),
  setPan: (pan) => set({ pan }),
  resetHUD: () => set({ zoom: DEFAULT_ZOOM, pan: DEFAULT_PAN }),

  effect: 'ascii',
  setEffect: (effect) => set({ effect }),

  tone: DEFAULT_TONE,
  updateTone: (patch) => set((s) => ({ tone: { ...s.tone, ...patch } })),
  resetTone: () => set({ tone: DEFAULT_TONE }),

  ascii: DEFAULT_ASCII,
  updateAscii: (patch) => set((s) => ({ ascii: { ...s.ascii, ...patch } })),

  theme: 'dark',
  toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),

  leftCollapsed: false,
  rightCollapsed: false,
  toggleLeftRail: () => set((s) => ({ leftCollapsed: !s.leftCollapsed })),
  toggleRightRail: () => set((s) => ({ rightCollapsed: !s.rightCollapsed })),

  setMedia: (media) => set(media),
  setDimensions: (dimensions) => set({ dimensions }),
}));

/** HUD zoom bounds: 10% .. 800% (interactive zoom buttons + wheel). */
export const ZOOM_MIN = 0.1;
export const ZOOM_MAX = 8;

function clampZoom(zoom: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom));
}
