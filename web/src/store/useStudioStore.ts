import { create } from 'zustand';
import type {
  AsciiSettings,
  Dimensions,
  EffectMode,
  EffectParams,
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

  // Dynamic effect parameters
  effectParams: EffectParams;
  updateEffectParam: (key: keyof EffectParams, value: number) => void;

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

  // Media ingestion (MEDIA-01, MEDIA-02, D-04)
  loadMediaFile: (file: File, expectedType?: 'image' | 'video') => Promise<void>;
  startWebcam: () => Promise<void>;
  stopWebcam: () => void;
  clearMedia: () => void;
  openFileBrowser: (filter?: 'image' | 'video') => void;
  setMedia: (media: Partial<MediaState>) => void;
  setDimensions: (dimensions: Dimensions) => void;

  // Video playback controls
  isPlaying: boolean;
  isMuted: boolean;
  playbackTime: number;
  duration: number;
  setIsPlaying: (playing: boolean) => void;
  setIsMuted: (muted: boolean) => void;
  setPlaybackTime: (time: number) => void;
  setDuration: (duration: number) => void;
  togglePlay: () => void;
  stopVideo: () => void;
  toggleMute: () => void;
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

export const DEFAULT_EFFECT_PARAMS: EffectParams = {
  ditherSteps: 4,
  ditherSpread: 0.5,
  halftoneFreq: 50,
  halftoneAngle: 45,
  halftoneRadius: 1.0,
  matrixSpeed: 1.0,
  matrixDensity: 40,
  sortThreshold: 0.5,
  sortSpan: 30,
  sortDirection: 0,
  genericA: 12,
  genericB: 0.2,
  vhsScanlineIntensity: 0.2,
  vhsAberration: 0.5,
  vhsNoiseIntensity: 0.1,
  vhsCurvature: 0.0,
};

const DEFAULT_PAN: Pan = { x: 0, y: 0 };
const DEFAULT_ZOOM = 1;

/** HUD zoom bounds: 10% .. 800% (interactive zoom buttons + wheel). */
export const ZOOM_MIN = 0.1;
export const ZOOM_MAX = 8;

function clampZoom(zoom: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom));
}

/**
 * Non-reactive media resources. MediaStream and object URLs must never live
 * in reactive state (T-02-03/T-02-04): they are disposed explicitly here.
 */
let activeObjectUrl: string | null = null;
let activeStream: MediaStream | null = null;
let registeredVideo: HTMLVideoElement | null = null;

/** CenterStage registers its persistent <video> element for stream feeds. */
export function registerVideoElement(el: HTMLVideoElement | null): void {
  registeredVideo = el;
  if (activeStream && el) {
    el.srcObject = activeStream;
    el.play().catch(() => undefined);
  }
}

/**
 * Dropzone registers its hidden file input so the LeftRail source buttons can
 * open the same browser picker (single ingestion entry point through
 * loadMediaFile).
 */
let browseHandler: ((filter?: 'image' | 'video') => void) | null = null;

export function registerBrowseHandler(fn: ((filter?: 'image' | 'video') => void) | null): void {
  browseHandler = fn;
}

function stopStream(): void {
  if (!activeStream) return;
  for (const track of activeStream.getTracks()) track.stop(); // camera indicator off (T-02-04)
  activeStream = null;
  if (registeredVideo) registeredVideo.srcObject = null;
}

function revokeUrl(): void {
  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl); // unbounded memory guard (T-02-03)
    activeObjectUrl = null;
  }
}

function detachMediaPlayback(): void {
  stopStream();
  revokeUrl();
}

function readImageDimensions(url: string): Promise<Dimensions> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () =>
      resolve({ width: img.naturalWidth, height: img.naturalHeight }); // native, uncapped (D-04)
    img.onerror = () => reject(new Error('image decode failed'));
    img.src = url;
  });
}

function readVideoDimensions(url: string): Promise<Dimensions> {
  return new Promise((resolve, reject) => {
    const probe = document.createElement('video');
    probe.preload = 'metadata';
    probe.onloadedmetadata = () => {
      resolve({ width: probe.videoWidth, height: probe.videoHeight });
      probe.removeAttribute('src');
    };
    probe.onerror = () => reject(new Error('video decode failed'));
    probe.src = url;
  });
}

export const useStudioStore = create<StudioState>()((set, get) => ({
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

  effectParams: DEFAULT_EFFECT_PARAMS,
  updateEffectParam: (key, value) =>
    set((s) => ({ effectParams: { ...s.effectParams, [key]: value } })),

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

  // Video playback
  isPlaying: false,
  isMuted: false,
  playbackTime: 0,
  duration: 0,
  setIsPlaying: (playing) => set({ isPlaying: playing }),
  setIsMuted: (muted) => {
    if (registeredVideo) registeredVideo.muted = muted;
    set({ isMuted: muted });
  },
  setPlaybackTime: (time) => set({ playbackTime: time }),
  setDuration: (duration) => set({ duration }),
  togglePlay: () => {
    if (!registeredVideo) return;
    if (registeredVideo.paused) {
      registeredVideo.play().then(() => set({ isPlaying: true })).catch(() => undefined);
    } else {
      registeredVideo.pause();
      set({ isPlaying: false });
    }
  },
  stopVideo: () => {
    if (!registeredVideo) return;
    registeredVideo.pause();
    registeredVideo.currentTime = 0;
    set({ isPlaying: false, playbackTime: 0 });
  },
  toggleMute: () => {
    if (!registeredVideo) return;
    const nextMuted = !registeredVideo.muted;
    registeredVideo.muted = nextMuted;
    set({ isMuted: nextMuted });
  },

  /** Image/video ingestion via local blob URL — same-origin, never tainted (Pitfall 2). */
  loadMediaFile: async (file, expectedType) => {
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const imageExts = ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'svg'];
    const videoExts = ['mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi'];
    const isImage = file.type.startsWith('image/') || imageExts.includes(ext);
    const isVideo = file.type.startsWith('video/') || videoExts.includes(ext);

    if (expectedType === 'image' && !isImage) {
      alert(`"${file.name}" is not an image file. Please select a PNG, JPG, WebP, or GIF image.`);
      return;
    }
    if (expectedType === 'video' && !isVideo) {
      alert(`"${file.name}" is not a video file. Please select an MP4 or WebM video.`);
      return;
    }
    if (!isImage && !isVideo) {
      alert(`Unsupported file format "${file.name}". Please upload an image or video.`);
      return;
    }

    stopWebcamInternal(set, get);
    revokeUrl();

    const url = URL.createObjectURL(file);
    activeObjectUrl = url;
    try {
      const dimensions = isImage
        ? await readImageDimensions(url)
        : await readVideoDimensions(url);
      set({
        mediaType: isImage ? 'image' : 'video',
        mediaUrl: url,
        mediaName: file.name,
        dimensions,
        isPlaying: isVideo,
        playbackTime: 0,
        duration: 0,
      });
      get().resetHUD(); // viewport fit: 100% zoom, centered
    } catch (err) {
      revokeUrl();
      console.warn('Media load failed:', err);
    }
  },

  /** Live webcam feed via getUserMedia (MEDIA-02). Same-origin stream. */
  startWebcam: async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      console.warn('getUserMedia unavailable in this browser');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      stopWebcamInternal(set, get);
      revokeUrl();
      activeStream = stream;

      const el = registeredVideo;
      if (el) {
        el.srcObject = stream;
        el.play().catch(() => undefined);
      }

      const track = stream.getVideoTracks()[0];
      const trackDims = track?.getSettings();
      const dimensions =
        trackDims?.width && trackDims?.height
          ? { width: trackDims.width, height: trackDims.height }
          : null;
      set({ mediaType: 'webcam', mediaUrl: null, mediaName: 'live webcam', dimensions });
      get().resetHUD();
    } catch (err) {
      console.warn('Webcam access denied or unavailable:', err);
    }
  },

  /** Stop all stream tracks and detach the video element (T-02-04). */
  stopWebcam: () => stopWebcamInternal(set, get),

  /** Return the studio to blank-slate standby (D-04). */
  clearMedia: () => {
    detachMediaPlayback();
    if (registeredVideo) {
      try {
        registeredVideo.pause();
        registeredVideo.removeAttribute('src');
        registeredVideo.load();
      } catch {
        // ignore
      }
    }
    set({
      mediaType: null,
      mediaUrl: null,
      mediaName: null,
      dimensions: null,
      isPlaying: false,
      playbackTime: 0,
      duration: 0,
    });
    get().resetHUD();
  },

  /** Open the shared hidden file input registered by Dropzone. */
  openFileBrowser: (filter?: 'image' | 'video') => {
    if (!browseHandler) {
      console.warn('File browser not registered yet (Dropzone not mounted)');
      return;
    }
    browseHandler(filter);
  },

  setMedia: (media) => set(media),
  setDimensions: (dimensions) => set({ dimensions }),
}));

function stopWebcamInternal(
  set: (partial: Partial<StudioState>) => void,
  get: () => StudioState,
): void {
  if (activeStream) {
    stopStream();
    // Only clear the webcam identity if the current media IS the webcam feed.
    if (get().mediaType === 'webcam') {
      set({
        mediaType: null,
        mediaUrl: null,
        mediaName: null,
        dimensions: null,
      });
    }
  }
}
