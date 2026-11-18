import * as THREE from 'three/webgpu';

export interface RendererOptions {
  canvas: HTMLCanvasElement;
  powerPreference?: 'high-performance' | 'low-power' | 'default';
  antialias?: boolean;
}

/**
 * Three.js WebGPURenderer lifecycle manager with automatic WebGL2 backend fallback (D-01, SHADER-04).
 */
export class StudioRenderer {
  private renderer: THREE.WebGPURenderer | null = null;
  private canvas: HTMLCanvasElement;
  private isWebGLFallback = false;

  constructor(options: RendererOptions) {
    this.canvas = options.canvas;
  }

  /**
   * Initializes the WebGPURenderer, attempting native WebGPU first.
   * If navigator.gpu is missing or renderer.init() rejects, falls back cleanly to forceWebGL: true.
   */
  async init(): Promise<void> {
    const hasWebGPU = typeof navigator !== 'undefined' && 'gpu' in navigator;

    if (hasWebGPU) {
      try {
        this.renderer = new THREE.WebGPURenderer({
          canvas: this.canvas,
          antialias: false,
          powerPreference: 'high-performance',
        });
        await this.renderer.init();
        this.isWebGLFallback = false;
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        return;
      } catch (err) {
        console.warn('WebGPU init failed, attempting WebGL2 fallback:', err);
        if (this.renderer) {
          try {
            this.renderer.dispose();
          } catch {
            // ignore cleanup errors during fallback switch
          }
        }
      }
    }

    // WebGL fallback path
    this.renderer = new THREE.WebGPURenderer({
      canvas: this.canvas,
      antialias: false,
      forceWebGL: true,
      powerPreference: 'high-performance',
    });
    await this.renderer.init();
    this.isWebGLFallback = true;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  }

  getRenderer(): THREE.WebGPURenderer {
    if (!this.renderer) {
      throw new Error('StudioRenderer not initialized. Call init() first.');
    }
    return this.renderer;
  }

  getIsWebGLFallback(): boolean {
    return this.isWebGLFallback;
  }

  setSize(width: number, height: number): void {
    if (this.renderer) {
      this.renderer.setSize(width, height, false);
    }
  }

  render(scene: THREE.Scene, camera: THREE.Camera): void {
    if (this.renderer) {
      this.renderer.render(scene, camera);
    }
  }

  dispose(): void {
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer = null;
    }
  }
}
