import {
  Fn,
  uv,
  vec3,
  vec4,
  sin,
  fract,
  clamp,
} from 'three/tsl';

export interface VhsNodeInputs {
  colorNode: any; // vec4 input color from previous stage
  scanlineIntensity: any; // uniform float (0..1)
  scanlineFrequency: any; // uniform float (e.g. 400..1200)
  aberration: any; // uniform float (chromatic aberration offset in px/normalized)
  noiseIntensity: any; // uniform float (0..1)
  time: any; // uniform float (seconds elapsed)
  curvature: any; // uniform float (0..1)
}

/**
 * VHS/CRT Post-FX Overlay shader node using TSL (SHADER-02, D-06 stage 4).
 * Combines:
 * 1. CRT barrel curvature distortion
 * 2. Horizontal scanlines simulation
 * 3. Chromatic aberration (RGB shift)
 * 4. Tape glitch & dynamic analog static noise
 * 5. Screen edge vignette darkening
 */
export const vhsShaderNode = (inputs: VhsNodeInputs) => {
  const {
    colorNode,
    scanlineIntensity,
    scanlineFrequency,
    aberration,
    noiseIntensity,
    time,
    curvature,
  } = inputs;

  return Fn(() => {
    const rawUV = uv();

    // 1. CRT Curvature distortion
    // center coordinates [-0.5, 0.5]
    const cc = rawUV.sub(0.5);
    const distSq = cc.x.mul(cc.x).add(cc.y.mul(cc.y));
    const distFactor = distSq.mul(curvature).add(1.0);
    const st = cc.mul(distFactor).add(0.5);

    // Check boundary - clamp to screen frame
    const inBounds = st.x.greaterThanEqual(0.0)
      .and(st.x.lessThanEqual(1.0))
      .and(st.y.greaterThanEqual(0.0))
      .and(st.y.lessThanEqual(1.0));

    // Base color from upstream node
    const baseColor = colorNode;
    const baseRGB = baseColor.rgb;

    // 2. Chromatic Aberration: shift red channel left, blue channel right
    const rShift = aberration;
    const bShift = aberration.negate();
    const rCol = clamp(baseRGB.r.add(sin(st.y.mul(100.0).add(time.mul(10.0))).mul(rShift)), 0.0, 1.0);
    const bCol = clamp(baseRGB.b.add(sin(st.y.mul(100.0).add(time.mul(10.0))).mul(bShift)), 0.0, 1.0);
    const rgbWithAberration: any = vec3(rCol, baseRGB.g, bCol);

    // 3. Scanline simulation: sin wave across vertical axis
    const scanline = sin(st.y.mul(scanlineFrequency).add(time.mul(2.0)))
      .mul(0.5)
      .add(0.5);
    const scanlineMultiplier = scanlineIntensity.mul(scanline.sub(1.0)).add(1.0);
    const rgbWithScanlines: any = rgbWithAberration.mul(scanlineMultiplier);

    // 4. Analog tape noise / static artifact
    const noiseSeed = st.x.mul(12.9898).add(st.y.mul(78.233)).add(time.mul(43.123));
    const noise = fract(sin(noiseSeed).mul(43758.5453));
    const noiseMod = noise.sub(0.5).mul(noiseIntensity);
    const rgbWithNoise: any = rgbWithScanlines.add(vec3(noiseMod));

    // 5. Vignette darkening towards corners
    const vigDist = distSq.mul(2.0);
    const vignette = clamp(vigDist.negate().add(1.0), 0.0, 1.0);
    const rgbWithVignette: any = rgbWithNoise.mul(vignette);

    // Darken out of bounds
    const finalRGB = inBounds.select(rgbWithVignette, vec3(0.0));

    return vec4(finalRGB, baseColor.a);
  })();
};
