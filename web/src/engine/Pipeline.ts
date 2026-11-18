import * as THREE from 'three/webgpu';
import {
  uniform,
  texture,
  vec2,
  vec4,
} from 'three/tsl';
import { StudioRenderer } from './Renderer';
import { TextureAtlas } from './TextureAtlas';
import { preToneNode } from './shaders/preTone';
import { asciiShaderNode } from './shaders/ascii';
import { vhsShaderNode } from './shaders/vhs';
import type { ToneSettings, AsciiSettings, EffectMode } from '../types/studio';

export interface PipelineOptions {
  canvas: HTMLCanvasElement;
}

export type ColorGradingPreset = 'original' | 'green' | 'amber' | 'cyan';

/**
 * 4-Stage Stage-Gated Shader Pipeline (D-06, SHADER-01, SHADER-02, SHADER-03, SHADER-04).
 * Stage 1: Pre-Tone Adjustments (Brightness, Contrast, Saturation, Hue Rotation, Gamma, Invert)
 * Stage 2: Primary Effect (ASCII, and extensible to other Grainrad modes in 02-04)
 * Stage 3: Color Grading (Original TrueColor, Phosphor Green, Amber CRT, Cyan Terminal)
 * Stage 4: Post-FX Overlay (CRT/VHS scanlines, tape glitch, chromatic aberration, curvature)
 */
export class StudioPipeline {
  private studioRenderer: StudioRenderer;
  private renderer: THREE.WebGPURenderer | null = null;
  private textureAtlas: TextureAtlas;

  // Scene & Display Mesh
  private scene: THREE.Scene;
  private camera: THREE.OrthographicCamera;
  private displayMaterial: THREE.MeshBasicNodeMaterial;
  private displayMesh: THREE.Mesh;

  // Input source texture
  private sourceTexture: THREE.Texture | null = null;
  private sourceTextureNode: any = null;

  // Uniforms
  private resolutionUniform: any;
  private timeUniform: any;

  // Tone Uniforms (Stage 1)
  private brightnessUniform: any;
  private contrastUniform: any;
  private saturationUniform: any;
  private hueRotationUniform: any;
  private gammaUniform: any;
  private invertUniform: any;

  // ASCII Uniforms (Stage 2)
  private cellScaleUniform: any;
  private charSpacingUniform: any;
  private charAspectUniform: any;
  private rampLengthUniform: any;

  // VHS/CRT Uniforms (Stage 4)
  private vhsScanlineIntensity: any;
  private vhsScanlineFrequency: any;
  private vhsAberration: any;
  private vhsNoiseIntensity: any;
  private vhsCurvature: any;

  private activeEffect: EffectMode = 'ascii';
  private colorGrading: ColorGradingPreset = 'original';
  private isDisposed = false;

  constructor(options: PipelineOptions) {
    this.studioRenderer = new StudioRenderer({ canvas: options.canvas });
    this.textureAtlas = new TextureAtlas();

    // Scene & Orthographic camera for full-screen quad display
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    // Initial uniform nodes
    this.resolutionUniform = uniform(vec2(1, 1));
    this.timeUniform = uniform(0);

    this.brightnessUniform = uniform(1.0);
    this.contrastUniform = uniform(1.0);
    this.saturationUniform = uniform(1.0);
    this.hueRotationUniform = uniform(0.0);
    this.gammaUniform = uniform(1.0);
    this.invertUniform = uniform(0.0);

    this.cellScaleUniform = uniform(8.0);
    this.charSpacingUniform = uniform(0.0);
    this.charAspectUniform = uniform(0.5);
    this.rampLengthUniform = uniform(10.0);

    this.vhsScanlineIntensity = uniform(0.0);
    this.vhsScanlineFrequency = uniform(800.0);
    this.vhsAberration = uniform(0.0);
    this.vhsNoiseIntensity = uniform(0.0);
    this.vhsCurvature = uniform(0.0);

    this.displayMaterial = new THREE.MeshBasicNodeMaterial();
    const planeGeo = new THREE.PlaneGeometry(2, 2);
    this.displayMesh = new THREE.Mesh(planeGeo, this.displayMaterial);
    this.scene.add(this.displayMesh);
  }

  async init(): Promise<void> {
    await this.studioRenderer.init();
    this.renderer = this.studioRenderer.getRenderer();
    this.textureAtlas.updateRamp('standard');
    this.rebuildPipeline();
  }

  /**
   * Sets or replaces the source media texture (image, video, or webcam).
   */
  setSourceTexture(tex: THREE.Texture): void {
    this.sourceTexture = tex;
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;
    this.sourceTextureNode = texture(tex);
    this.rebuildPipeline();
  }

  /**
   * Syncs ToneSettings from Zustand store to uniforms.
   */
  updateTone(settings: ToneSettings): void {
    this.brightnessUniform.value = settings.brightness;
    this.contrastUniform.value = settings.contrast;
    this.saturationUniform.value = settings.saturation;
    this.hueRotationUniform.value = settings.hueRotation;
    this.gammaUniform.value = settings.gamma;
    this.invertUniform.value = settings.invert ? 1.0 : 0.0;
  }

  /**
   * Syncs AsciiSettings from Zustand store to uniforms and updates texture atlas.
   */
  updateAscii(settings: AsciiSettings): void {
    this.cellScaleUniform.value = settings.cellScale;
    this.charSpacingUniform.value = settings.charSpacing;
    this.charAspectUniform.value = settings.charAspect;

    this.textureAtlas.updateRamp(settings.rampPreset, settings.customChars);
    this.rampLengthUniform.value = this.textureAtlas.getCharCount();
  }

  /**
   * Updates VHS overlay parameters.
   */
  updateVhs(options: {
    scanlineIntensity?: number;
    scanlineFrequency?: number;
    aberration?: number;
    noiseIntensity?: number;
    curvature?: number;
  }): void {
    if (options.scanlineIntensity !== undefined) this.vhsScanlineIntensity.value = options.scanlineIntensity;
    if (options.scanlineFrequency !== undefined) this.vhsScanlineFrequency.value = options.scanlineFrequency;
    if (options.aberration !== undefined) this.vhsAberration.value = options.aberration;
    if (options.noiseIntensity !== undefined) this.vhsNoiseIntensity.value = options.noiseIntensity;
    if (options.curvature !== undefined) this.vhsCurvature.value = options.curvature;
  }

  setEffect(effect: EffectMode): void {
    if (this.activeEffect !== effect) {
      this.activeEffect = effect;
      this.rebuildPipeline();
    }
  }

  setColorGrading(preset: ColorGradingPreset): void {
    if (this.colorGrading !== preset) {
      this.colorGrading = preset;
      this.rebuildPipeline();
    }
  }

  /**
   * Assembles the 4-stage pipeline graph:
   * Source -> Stage 1 (PreTone) -> Stage 2 (Primary Effect) -> Stage 3 (Color Grading) -> Stage 4 (Post-FX)
   */
  private rebuildPipeline(): void {
    if (!this.sourceTextureNode) {
      // Standby color when no media is loaded
      this.displayMaterial.colorNode = vec4(0.06, 0.06, 0.06, 1.0);
      this.displayMaterial.needsUpdate = true;
      return;
    }

    // Stage 1: Pre-Tone Node
    const preToneOut = preToneNode({
      colorNode: this.sourceTextureNode,
      brightness: this.brightnessUniform,
      contrast: this.contrastUniform,
      saturation: this.saturationUniform,
      hueRotation: this.hueRotationUniform,
      gamma: this.gammaUniform,
      invert: this.invertUniform,
    });

    // Stage 2: Primary Effect
    let effectOut: any = preToneOut;

    if (this.activeEffect === 'ascii') {
      const atlasTexNode = texture(this.textureAtlas.getTexture());
      effectOut = asciiShaderNode({
        sourceNode: preToneOut,
        atlasTexture: atlasTexNode,
        cellScale: this.cellScaleUniform,
        charSpacing: this.charSpacingUniform,
        charAspect: this.charAspectUniform,
        rampLength: this.rampLengthUniform,
        resolution: this.resolutionUniform,
      });
    }

    // Stage 3: Color Grading (Phosphor Green, Amber CRT, Cyan Terminal, Original)
    let gradedOut: any = effectOut;
    if (this.colorGrading === 'green') {
      // Rec. 601 lum tinted with Phosphor Green #33ff33
      const lum = effectOut.r.mul(0.299).add(effectOut.g.mul(0.587)).add(effectOut.b.mul(0.114));
      gradedOut = vec4(lum.mul(0.2), lum.mul(1.0), lum.mul(0.2), effectOut.a);
    } else if (this.colorGrading === 'amber') {
      // Amber CRT #ffb000
      const lum = effectOut.r.mul(0.299).add(effectOut.g.mul(0.587)).add(effectOut.b.mul(0.114));
      gradedOut = vec4(lum.mul(1.0), lum.mul(0.69), lum.mul(0.0), effectOut.a);
    } else if (this.colorGrading === 'cyan') {
      // Cyan Terminal #00f0ff
      const lum = effectOut.r.mul(0.299).add(effectOut.g.mul(0.587)).add(effectOut.b.mul(0.114));
      gradedOut = vec4(lum.mul(0.0), lum.mul(0.94), lum.mul(1.0), effectOut.a);
    }

    // Stage 4: Post-FX Overlay (CRT/VHS)
    const finalOut = vhsShaderNode({
      colorNode: gradedOut,
      scanlineIntensity: this.vhsScanlineIntensity,
      scanlineFrequency: this.vhsScanlineFrequency,
      aberration: this.vhsAberration,
      noiseIntensity: this.vhsNoiseIntensity,
      time: this.timeUniform,
      curvature: this.vhsCurvature,
    });

    this.displayMaterial.colorNode = finalOut;
    this.displayMaterial.needsUpdate = true;
  }

  resize(width: number, height: number): void {
    if (width <= 0 || height <= 0) return;
    this.resolutionUniform.value.set(width, height);
    this.studioRenderer.setSize(width, height);
  }

  render(timeSeconds: number = 0): void {
    if (this.isDisposed || !this.renderer) return;
    this.timeUniform.value = timeSeconds;

    if (this.sourceTexture instanceof THREE.VideoTexture) {
      this.sourceTexture.needsUpdate = true;
    }

    this.renderer.render(this.scene, this.camera);
  }

  getRenderer(): StudioRenderer {
    return this.studioRenderer;
  }

  dispose(): void {
    this.isDisposed = true;
    this.textureAtlas.dispose();
    this.displayMaterial.dispose();
    this.displayMesh.geometry.dispose();
    this.studioRenderer.dispose();
  }
}
