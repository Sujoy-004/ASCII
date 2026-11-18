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
import { ditherShaderNode } from './shaders/dither';
import { halftoneShaderNode } from './shaders/halftone';
import { matrixRainShaderNode } from './shaders/matrixRain';
import { pixelSortShaderNode } from './shaders/pixelSort';
import { vhsShaderNode } from './shaders/vhs';
import {
  dotsShaderNode,
  contourShaderNode,
  blockifyShaderNode,
  thresholdShaderNode,
  edgeDetectShaderNode,
  crosshatchShaderNode,
  waveLinesShaderNode,
  noiseFieldShaderNode,
  voronoiShaderNode,
} from './shaders/effects';
import type { ToneSettings, AsciiSettings, EffectMode } from '../types/studio';

export interface PipelineOptions {
  canvas: HTMLCanvasElement;
}

export type ColorGradingPreset = 'original' | 'green' | 'amber' | 'cyan';

/**
 * 4-Stage Stage-Gated Shader Pipeline supporting all 16 Grainrad Modes (D-02, D-06, SHADER-01, SHADER-02, SHADER-03, SHADER-04).
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

  // Shared Uniforms
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

  // Dither Uniforms
  private ditherMatrixType: any;
  private ditherColorSteps: any;
  private ditherSpread: any;

  // Halftone Uniforms
  private halftoneFrequency: any;
  private halftoneAngle: any;
  private halftoneDotRadius: any;

  // Matrix Rain Uniforms
  private matrixSpeed: any;
  private matrixDropLength: any;
  private matrixDensity: any;

  // Pixel Sort Uniforms
  private sortThreshold: any;
  private sortSpan: any;
  private sortDirection: any;

  // Generic Effect Uniforms
  private genericParamA: any;
  private genericParamB: any;

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

    this.ditherMatrixType = uniform(1.0);
    this.ditherColorSteps = uniform(4.0);
    this.ditherSpread = uniform(0.5);

    this.halftoneFrequency = uniform(50.0);
    this.halftoneAngle = uniform(45.0);
    this.halftoneDotRadius = uniform(1.0);

    this.matrixSpeed = uniform(1.0);
    this.matrixDropLength = uniform(15.0);
    this.matrixDensity = uniform(40.0);

    this.sortThreshold = uniform(0.5);
    this.sortSpan = uniform(20.0);
    this.sortDirection = uniform(0.0);

    this.genericParamA = uniform(8.0);
    this.genericParamB = uniform(1.0);

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

  setSourceTexture(tex: THREE.Texture): void {
    this.sourceTexture = tex;
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;
    this.sourceTextureNode = texture(tex);
    this.rebuildPipeline();
  }

  clearSource(): void {
    if (this.sourceTexture) {
      this.sourceTexture.dispose();
      this.sourceTexture = null;
    }
    this.sourceTextureNode = null;
    this.rebuildPipeline();
  }

  updateTone(settings: ToneSettings): void {
    this.brightnessUniform.value = settings.brightness;
    this.contrastUniform.value = settings.contrast;
    this.saturationUniform.value = settings.saturation;
    this.hueRotationUniform.value = settings.hueRotation;
    this.gammaUniform.value = settings.gamma;
    this.invertUniform.value = settings.invert ? 1.0 : 0.0;
  }

  updateAscii(settings: AsciiSettings): void {
    this.cellScaleUniform.value = settings.cellScale;
    this.charSpacingUniform.value = settings.charSpacing;
    this.charAspectUniform.value = settings.charAspect;

    this.textureAtlas.updateRamp(settings.rampPreset, settings.customChars);
    this.rampLengthUniform.value = this.textureAtlas.getCharCount();
  }

  updateEffectParam(key: string, value: number): void {
    switch (key) {
      case 'ditherSteps': this.ditherColorSteps.value = value; break;
      case 'ditherSpread': this.ditherSpread.value = value; break;
      case 'halftoneFreq': this.halftoneFrequency.value = value; break;
      case 'halftoneAngle': this.halftoneAngle.value = value; break;
      case 'halftoneRadius': this.halftoneDotRadius.value = value; break;
      case 'matrixSpeed': this.matrixSpeed.value = value; break;
      case 'matrixDensity': this.matrixDensity.value = value; break;
      case 'sortThreshold': this.sortThreshold.value = value; break;
      case 'sortSpan': this.sortSpan.value = value; break;
      case 'sortDirection': this.sortDirection.value = value; break;
      case 'genericA': this.genericParamA.value = value; break;
      case 'genericB': this.genericParamB.value = value; break;
      case 'vhsScanlineIntensity': this.vhsScanlineIntensity.value = value; break;
      case 'vhsAberration': this.vhsAberration.value = value; break;
      case 'vhsNoiseIntensity': this.vhsNoiseIntensity.value = value; break;
      case 'vhsCurvature': this.vhsCurvature.value = value; break;
    }
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

  private rebuildPipeline(): void {
    if (!this.sourceTextureNode) {
      this.displayMaterial.colorNode = vec4(0.06, 0.06, 0.06, 1.0);
      this.displayMaterial.needsUpdate = true;
      return;
    }

    // Stage 1: Pre-Tone sampler (supports custom UV coordinates for spatial shaders)
    const samplePreTone = (customUV?: any) => {
      const srcNode = customUV && this.sourceTexture
        ? texture(this.sourceTexture, customUV)
        : this.sourceTextureNode;
      return preToneNode({
        colorNode: srcNode,
        brightness: this.brightnessUniform,
        contrast: this.contrastUniform,
        saturation: this.saturationUniform,
        hueRotation: this.hueRotationUniform,
        gamma: this.gammaUniform,
        invert: this.invertUniform,
      });
    };

    const preToneOut = samplePreTone();

    // Stage 2: 16 Grainrad Primary Effect Switching (D-02)
    let effectOut: any = preToneOut;

    switch (this.activeEffect) {
      case 'ascii': {
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
        break;
      }
      case 'dither':
        effectOut = ditherShaderNode({
          colorNode: preToneOut,
          matrixType: this.ditherMatrixType,
          colorSteps: this.ditherColorSteps,
          resolution: this.resolutionUniform,
          spread: this.ditherSpread,
        });
        break;
      case 'halftone':
        effectOut = halftoneShaderNode({
          colorNode: preToneOut,
          frequency: this.halftoneFrequency,
          angle: this.halftoneAngle,
          dotRadius: this.halftoneDotRadius,
          resolution: this.resolutionUniform,
        });
        break;
      case 'matrix':
        effectOut = matrixRainShaderNode({
          colorNode: preToneOut,
          speed: this.matrixSpeed,
          dropLength: this.matrixDropLength,
          density: this.matrixDensity,
          time: this.timeUniform,
          resolution: this.resolutionUniform,
        });
        break;
      case 'pixelSort':
        effectOut = pixelSortShaderNode({
          sampleAt: samplePreTone,
          threshold: this.sortThreshold,
          sortSpan: this.sortSpan,
          direction: this.sortDirection,
          resolution: this.resolutionUniform,
          time: this.timeUniform,
        });
        break;
      case 'dots':
        effectOut = dotsShaderNode({
          colorNode: preToneOut,
          spacing: this.genericParamA,
          radius: this.genericParamB,
          resolution: this.resolutionUniform,
        });
        break;
      case 'contour':
        effectOut = contourShaderNode({
          colorNode: preToneOut,
          steps: this.genericParamA,
          lineWidth: this.genericParamB.mul(0.1),
        });
        break;
      case 'blockify':
        effectOut = blockifyShaderNode({
          sampleAt: samplePreTone,
          blockSize: this.genericParamA,
          gridLine: this.genericParamB,
          resolution: this.resolutionUniform,
        });
        break;
      case 'threshold':
        effectOut = thresholdShaderNode({
          colorNode: preToneOut,
          threshold: this.genericParamB.mul(0.5),
        });
        break;
      case 'edgeDetect':
        effectOut = edgeDetectShaderNode({
          colorNode: preToneOut,
          sensitivity: this.genericParamA,
        });
        break;
      case 'crosshatch':
        effectOut = crosshatchShaderNode({
          colorNode: preToneOut,
          spacing: this.genericParamA,
          resolution: this.resolutionUniform,
        });
        break;
      case 'waveLines':
        effectOut = waveLinesShaderNode({
          colorNode: preToneOut,
          frequency: this.genericParamA,
          amplitude: this.genericParamB,
          time: this.timeUniform,
        });
        break;
      case 'noise':
        effectOut = noiseFieldShaderNode({
          colorNode: preToneOut,
          intensity: this.genericParamB,
          time: this.timeUniform,
        });
        break;
      case 'voronoi':
        effectOut = voronoiShaderNode({
          colorNode: preToneOut,
          scale: this.genericParamA,
          resolution: this.resolutionUniform,
        });
        break;
      case 'vhs':
      case 'tone':
      default:
        effectOut = preToneOut;
        break;
    }

    // Stage 3: Color Grading
    let gradedOut: any = effectOut;
    if (this.colorGrading === 'green') {
      const lum = effectOut.r.mul(0.299).add(effectOut.g.mul(0.587)).add(effectOut.b.mul(0.114));
      gradedOut = vec4(lum.mul(0.2), lum.mul(1.0), lum.mul(0.2), effectOut.a);
    } else if (this.colorGrading === 'amber') {
      const lum = effectOut.r.mul(0.299).add(effectOut.g.mul(0.587)).add(effectOut.b.mul(0.114));
      gradedOut = vec4(lum.mul(1.0), lum.mul(0.69), lum.mul(0.0), effectOut.a);
    } else if (this.colorGrading === 'cyan') {
      const lum = effectOut.r.mul(0.299).add(effectOut.g.mul(0.587)).add(effectOut.b.mul(0.114));
      gradedOut = vec4(lum.mul(0.0), lum.mul(0.94), lum.mul(1.0), effectOut.a);
    }

    // Stage 4: Post-FX Overlay
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
      const vid = this.sourceTexture.image as HTMLVideoElement | undefined;
      if (vid && vid.readyState >= 2) {
        this.sourceTexture.needsUpdate = true;
      }
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
