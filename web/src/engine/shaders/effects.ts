import {
  Fn,
  uv,
  vec3,
  vec4,
  floor,
  fract,
  sin,
  clamp,
  float,
} from 'three/tsl';

// 1. Dots
export const dotsShaderNode = (inputs: { colorNode: any; spacing: any; radius: any; resolution: any }) => {
  const { colorNode, spacing, radius, resolution } = inputs;
  return Fn(() => {
    const st = uv();
    const pixelCoord = st.mul(resolution);
    const cell = fract(pixelCoord.div(spacing)).sub(0.5);
    const dist = cell.length();

    const baseCol = colorNode;
    const lum = baseCol.r.mul(0.299).add(baseCol.g.mul(0.587)).add(baseCol.b.mul(0.114));
    const dotR = lum.mul(radius).mul(0.5);
    const dotMask = dist.lessThanEqual(dotR).select(1.0, 0.0);

    return vec4(baseCol.rgb.mul(dotMask), baseCol.a);
  })();
};

// 2. Contour
export const contourShaderNode = (inputs: { colorNode: any; steps: any; lineWidth: any }) => {
  const { colorNode, steps, lineWidth } = inputs;
  return Fn(() => {
    const baseCol = colorNode;
    const lum = baseCol.r.mul(0.299).add(baseCol.g.mul(0.587)).add(baseCol.b.mul(0.114));

    const stepVal = fract(lum.mul(steps));
    const lineMask = stepVal.lessThan(lineWidth).select(1.0, 0.0);
    const contourCol = vec3(lineMask).mul(baseCol.rgb);

    return vec4(contourCol, baseCol.a);
  })();
};

// 3. Blockify (Pixelation / Mosaic with optional grid line)
export const blockifyShaderNode = (inputs: {
  sampleAt: (uvCoord: any) => any;
  blockSize: any;
  gridLine?: any;
  resolution: any;
}) => {
  const { sampleAt, blockSize, gridLine, resolution } = inputs;
  return Fn(() => {
    const st = uv();
    const pixelCoord = st.mul(resolution);
    const b = blockSize.max(2.0);
    const cellCoord = floor(pixelCoord.div(b));
    const cellCenterPx = cellCoord.mul(b).add(b.mul(0.5));
    const cellCenterUV = cellCenterPx.div(resolution);

    const baseCol = sampleAt(cellCenterUV);

    if (gridLine) {
      const cellFrac = fract(pixelCoord.div(b));
      const borderX = cellFrac.x.lessThan(b.reciprocal()).or(cellFrac.x.greaterThan(float(1.0).sub(b.reciprocal())));
      const borderY = cellFrac.y.lessThan(b.reciprocal()).or(cellFrac.y.greaterThan(float(1.0).sub(b.reciprocal())));
      const isBorder = borderX.or(borderY);
      const gridDim = float(1.0).sub(gridLine.mul(0.5));
      const finalRGB = isBorder.select(baseCol.rgb.mul(gridDim), baseCol.rgb);
      return vec4(finalRGB, baseCol.a);
    }

    return vec4(baseCol.rgb, baseCol.a);
  })();
};

// 4. Threshold
export const thresholdShaderNode = (inputs: { colorNode: any; threshold: any }) => {
  const { colorNode, threshold } = inputs;
  return Fn(() => {
    const baseCol = colorNode;
    const lum = baseCol.r.mul(0.299).add(baseCol.g.mul(0.587)).add(baseCol.b.mul(0.114));
    const isAbove = lum.greaterThanEqual(threshold);
    const binColor = isAbove.select(vec3(1.0), vec3(0.0));
    return vec4(binColor, baseCol.a);
  })();
};

// 5. Edge Detection
export const edgeDetectShaderNode = (inputs: { colorNode: any; sensitivity: any }) => {
  const { colorNode, sensitivity } = inputs;
  return Fn(() => {
    const baseCol = colorNode;
    const lum = baseCol.r.mul(0.299).add(baseCol.g.mul(0.587)).add(baseCol.b.mul(0.114));
    const edge = lum.mul(sensitivity).fract();
    const edgeRGB = vec3(edge);
    return vec4(edgeRGB, baseCol.a);
  })();
};

// 6. Crosshatch
export const crosshatchShaderNode = (inputs: { colorNode: any; spacing: any; resolution: any }) => {
  const { colorNode, spacing, resolution } = inputs;
  return Fn(() => {
    const st = uv();
    const pixelCoord = st.mul(resolution);
    const baseCol = colorNode;
    const lum = baseCol.r.mul(0.299).add(baseCol.g.mul(0.587)).add(baseCol.b.mul(0.114));

    const hatch1 = fract(pixelCoord.x.add(pixelCoord.y).div(spacing)).lessThan(0.2);
    const hatch2 = fract(pixelCoord.x.sub(pixelCoord.y).div(spacing)).lessThan(0.2);

    const lineVal = lum.lessThan(0.7).and(hatch1)
      .or(lum.lessThan(0.4).and(hatch2));

    const outCol = lineVal.select(vec3(0.0), vec3(1.0));
    return vec4(outCol, baseCol.a);
  })();
};

// 7. Wave Lines
export const waveLinesShaderNode = (inputs: { colorNode: any; frequency: any; amplitude: any; time: any }) => {
  const { colorNode, frequency, amplitude, time } = inputs;
  return Fn(() => {
    const st = uv();
    const wave = sin(st.y.mul(frequency).add(time.mul(2.0))).mul(amplitude);
    const waveMask = sin(st.x.mul(100.0).add(wave)).mul(0.5).add(0.5);

    const baseCol = colorNode;
    const finalRGB = baseCol.rgb.mul(waveMask);
    return vec4(finalRGB, baseCol.a);
  })();
};

// 8. Noise Field
export const noiseFieldShaderNode = (inputs: { colorNode: any; intensity: any; time: any }) => {
  const { colorNode, intensity, time } = inputs;
  return Fn(() => {
    const st = uv();
    const seed = st.x.mul(12.9898).add(st.y.mul(78.233)).add(time.mul(10.0));
    const noise = fract(sin(seed).mul(43758.5453)).sub(0.5).mul(intensity);

    const baseCol = colorNode;
    const finalRGB = clamp(baseCol.rgb.add(vec3(noise)), 0.0, 1.0);
    return vec4(finalRGB, baseCol.a);
  })();
};

// 9. Voronoi
export const voronoiShaderNode = (inputs: { colorNode: any; scale: any; resolution: any }) => {
  const { colorNode, scale, resolution } = inputs;
  return Fn(() => {
    const st = uv();
    const p = st.mul(resolution).div(scale);
    const f = fract(p).sub(0.5);
    const dist = f.length();

    const baseCol = colorNode;
    const finalRGB = baseCol.rgb.mul(dist.min(1.0));
    return vec4(finalRGB, baseCol.a);
  })();
};
