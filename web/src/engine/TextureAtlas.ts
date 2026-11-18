import * as THREE from 'three/webgpu';
import { CHAR_PRESETS } from '../store/presets';
import type { RampPreset } from '../types/studio';

export interface TextureAtlasOptions {
  fontSize?: number;
  fontFamily?: string;
}

/**
 * Dynamic monospace character texture atlas generator.
 * Renders characters in the active ramp into an offscreen 2D canvas strip
 * and uploads it as a CanvasTexture with nearest-neighbor filtering (D-07, SHADER-01).
 */
export class TextureAtlas {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private texture: THREE.CanvasTexture;
  private currentChars = '';
  private fontSize: number;
  private fontFamily: string;
  private charWidth = 0;
  private charHeight = 0;

  constructor(options: TextureAtlasOptions = {}) {
    this.fontSize = options.fontSize ?? 32;
    this.fontFamily = options.fontFamily ?? 'monospace, Courier New, Consolas';
    this.canvas = document.createElement('canvas');
    const context = this.canvas.getContext('2d', { willReadFrequently: false });
    if (!context) {
      throw new Error('Failed to get 2D context for character texture atlas');
    }
    this.ctx = context;

    this.texture = new THREE.CanvasTexture(this.canvas);
    this.texture.minFilter = THREE.NearestFilter;
    this.texture.magFilter = THREE.NearestFilter;
    this.texture.generateMipmaps = false;
  }

  /**
   * Updates the atlas texture for the given preset or custom character string.
   */
  updateRamp(preset: RampPreset, customChars?: string): void {
    const chars = customChars && customChars.length > 0 ? customChars : CHAR_PRESETS[preset];
    if (chars === this.currentChars && this.canvas.width > 0) {
      return;
    }
    this.currentChars = chars;

    // Measure character dimensions
    this.ctx.font = `${this.fontSize}px ${this.fontFamily}`;
    this.ctx.textBaseline = 'middle';
    this.ctx.textAlign = 'center';

    const sampleMetric = this.ctx.measureText('M');
    this.charWidth = Math.ceil(sampleMetric.width || this.fontSize * 0.6);
    this.charHeight = Math.ceil(this.fontSize);

    const count = chars.length;
    this.canvas.width = Math.max(1, count * this.charWidth);
    this.canvas.height = Math.max(1, this.charHeight);

    // Re-set font state after canvas resize
    this.ctx.fillStyle = '#000000';
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    this.ctx.font = `${this.fontSize}px ${this.fontFamily}`;
    this.ctx.textBaseline = 'middle';
    this.ctx.textAlign = 'center';
    this.ctx.fillStyle = '#ffffff';

    const centerY = this.charHeight / 2;
    for (let i = 0; i < count; i++) {
      const char = chars[i];
      const centerX = i * this.charWidth + this.charWidth / 2;
      this.ctx.fillText(char, centerX, centerY);
    }

    this.texture.needsUpdate = true;
  }

  getTexture(): THREE.CanvasTexture {
    return this.texture;
  }

  getCharCount(): number {
    return Math.max(1, this.currentChars.length);
  }

  getCharWidth(): number {
    return this.charWidth;
  }

  getCharHeight(): number {
    return this.charHeight;
  }

  dispose(): void {
    this.texture.dispose();
  }
}
