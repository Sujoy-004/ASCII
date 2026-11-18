import {
  Fn,
  uv,
  vec4,
  floor,
  clamp,
} from 'three/tsl';

export interface DitherNodeInputs {
  colorNode: any;
  matrixType: any;
  colorSteps: any;
  resolution: any;
  spread: any;
}

/**
 * Bayer 4x4 threshold matrix lookup in TSL.
 */
export const ditherShaderNode = (inputs: DitherNodeInputs) => {
  const {
    colorNode,
    colorSteps,
    resolution,
    spread,
  } = inputs;

  return Fn(() => {
    const st = uv();
    const pixelCoord = floor(st.mul(resolution));

    const x = pixelCoord.x.mod(4.0);
    const y = pixelCoord.y.mod(4.0);

    const x2 = floor(x.div(2.0));
    const y2 = floor(y.div(2.0));
    const x1 = x.mod(2.0);
    const y1 = y.mod(2.0);

    const b2 = y1.mul(2.0).add(x1);
    const b4 = y2.mul(2.0).add(x2);
    const bVal = b4.mul(4.0).add(b2).div(16.0).sub(0.5);

    const baseCol = colorNode;
    const rgb = baseCol.rgb;

    const ditherOffset = bVal.mul(spread);
    const ditheredRGB = rgb.add(ditherOffset);

    const stepsMinus1 = colorSteps.sub(1.0).max(1.0);
    const quantized = floor(ditheredRGB.mul(stepsMinus1).add(0.5)).div(stepsMinus1);
    const finalRGB = clamp(quantized, 0.0, 1.0);

    return vec4(finalRGB, baseCol.a);
  })();
};
