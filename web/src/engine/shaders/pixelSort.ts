import {
  Fn,
  uv,
  vec2,
  vec4,
  floor,
  fract,
  sin,
  float,
} from 'three/tsl';

export interface PixelSortInputs {
  sampleAt: (uvCoord: any) => any;
  threshold: any;
  sortSpan: any;
  direction: any;
  resolution: any;
  time: any;
}

/**
 * Pixel Sort directional luminance streak shader (D-02, D-05).
 * Inspects scanlines along the sort direction. When pixels exceed the luminance threshold,
 * smears and sorts the brightest upstream pixels into dynamic glitch intervals.
 */
export const pixelSortShaderNode = (inputs: PixelSortInputs) => {
  const {
    sampleAt,
    threshold,
    sortSpan,
    direction,
    resolution,
    time,
  } = inputs;

  return Fn(() => {
    const st = uv();
    const px = st.mul(resolution);

    const baseCol = sampleAt(st);
    const baseLum = baseCol.r.mul(0.299).add(baseCol.g.mul(0.587)).add(baseCol.b.mul(0.114));

    // direction: 0 = horizontal (left-to-right), 1 = vertical (top-to-bottom dripping)
    const isVert = direction.greaterThan(0.5);
    const dir = isVert.select(vec2(0.0, 1.0), vec2(1.0, 0.0));
    const scanAxis = isVert.select(px.x, px.y);

    // Per-scanline noise for organic streak intervals
    const rowSeed = floor(scanAxis);
    const rowNoise = fract(sin(rowSeed.mul(12.9898).add(time.mul(0.1))).mul(43758.5453));
    const effThresh = threshold.add(rowNoise.sub(0.5).mul(0.25)).clamp(0.05, 0.95);
    const effSpan = sortSpan.mul(rowNoise.mul(0.8).add(0.4));

    let hasSorted = baseLum.greaterThanEqual(effThresh);
    let bestCol = baseCol;
    let bestLum = baseLum;

    // Multi-tap directional search along the sort streak
    for (let i = 1; i <= 8; i++) {
      const stepOffset = effSpan.mul(float(i / 8.0));
      const samplePx = px.sub(dir.mul(stepOffset));
      const sampleUV = samplePx.div(resolution).clamp(0.0, 1.0);
      const sCol = sampleAt(sampleUV);
      const sLum = sCol.r.mul(0.299).add(sCol.g.mul(0.587)).add(sCol.b.mul(0.114));

      const isSampleAbove = sLum.greaterThanEqual(effThresh);
      hasSorted = hasSorted.or(isSampleAbove);

      const takeThis = sLum.greaterThan(bestLum).and(isSampleAbove);
      bestCol = takeThis.select(sCol, bestCol);
      bestLum = takeThis.select(sLum, bestLum);
    }

    const finalRGB = hasSorted.select(bestCol.rgb, baseCol.rgb);
    return vec4(finalRGB, baseCol.a);
  })();
};
