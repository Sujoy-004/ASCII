import {
  Fn,
  uv,
  vec2,
  vec4,
  fract,
  float,
} from 'three/tsl';

export interface HalftoneNodeInputs {
  colorNode: any;
  frequency: any;
  angle: any;
  dotRadius: any;
  resolution: any;
}

/**
 * Halftone dot screen shader with rotating parametric grid (SHADER-02).
 */
export const halftoneShaderNode = (inputs: HalftoneNodeInputs) => {
  const {
    colorNode,
    frequency,
    angle,
    dotRadius,
  } = inputs;

  return Fn(() => {
    const st: any = uv();

    const rad: any = angle.mul(0.017453292519943295);
    const cosA: any = rad.cos();
    const sinA: any = rad.sin();

    const centeredUV: any = st.sub(0.5);

    const rotX: any = centeredUV.x.mul(cosA).sub(centeredUV.y.mul(sinA));
    const rotY: any = centeredUV.x.mul(sinA).add(centeredUV.y.mul(cosA));
    const rotatedUV: any = vec2(rotX, rotY);

    const gridCoord: any = fract(rotatedUV.mul(frequency)).sub(0.5);
    const distToCenter: any = gridCoord.length();

    const baseCol: any = colorNode;
    const rgb: any = baseCol.rgb;

    const lum: any = rgb.r.mul(0.299).add(rgb.g.mul(0.587)).add(rgb.b.mul(0.114));

    const targetRadius: any = lum.mul(dotRadius).mul(0.5).clamp(0.0, 0.7);

    // Step-based dot mask
    const edge: any = distToCenter.lessThanEqual(targetRadius).select(float(1.0), float(0.0));

    const finalRGB: any = rgb.mul(edge);
    return vec4(finalRGB, baseCol.a);
  })();
};
