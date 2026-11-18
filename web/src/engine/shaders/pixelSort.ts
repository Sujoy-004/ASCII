import {
  Fn,
  uv,
  vec4,
  floor,
  fract,
  sin,
  clamp,
} from 'three/tsl';

export interface PixelSortInputs {
  colorNode: any;
  threshold: any;
  sortSpan: any;
  direction: any;
  resolution: any;
  time: any;
}

/**
 * Pixel Sort directional luminance streak shader (D-02, D-05).
 */
export const pixelSortShaderNode = (inputs: PixelSortInputs) => {
  const {
    colorNode,
    threshold,
    sortSpan,
    resolution,
    time,
  } = inputs;

  return Fn(() => {
    const st = uv();
    const baseCol = colorNode;
    const rgb = baseCol.rgb;

    const lum = rgb.r.mul(0.299).add(rgb.g.mul(0.587)).add(rgb.b.mul(0.114));

    const isAbove = lum.greaterThanEqual(threshold);

    const spanNorm = sortSpan.div(resolution.x);
    const seed = floor(st.y.mul(resolution.y)).mul(12.9898);
    const jitter = fract(sin(seed.add(time)).mul(43758.5453)).mul(spanNorm);

    const sortedRGB = isAbove.select(rgb.mul(jitter.add(1.0)), rgb);

    return vec4(clamp(sortedRGB, 0.0, 1.0), baseCol.a);
  })();
};
