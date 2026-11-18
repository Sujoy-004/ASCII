import {
  Fn,
  uv,
  vec3,
  vec4,
  floor,
  fract,
  sin,
  clamp,
} from 'three/tsl';

export interface MatrixRainInputs {
  colorNode: any;
  speed: any;
  dropLength: any;
  density: any;
  time: any;
  resolution: any;
}

/**
 * Matrix Rain animated phosphor green stream shader (D-02).
 */
export const matrixRainShaderNode = (inputs: MatrixRainInputs) => {
  const {
    colorNode,
    speed,
    dropLength,
    density,
    time,
  } = inputs;

  return Fn(() => {
    const st = uv();

    const colCount = density.max(10.0);
    const colIdx = floor(st.x.mul(colCount));

    const colRand = fract(sin(colIdx.mul(12.9898)).mul(43758.5453));
    const effectiveSpeed = speed.mul(colRand.mul(0.5).add(0.75));

    const streamY = fract(st.y.add(time.mul(effectiveSpeed)).add(colRand));

    const trail = fract(streamY.mul(dropLength));
    const intensity = trail.pow(3.0);

    const baseCol = colorNode;
    const lum = baseCol.r.mul(0.299).add(baseCol.g.mul(0.587)).add(baseCol.b.mul(0.114));

    const greenTail = vec3(0.0, 1.0, 0.4).mul(intensity).mul(lum);
    const whiteHead = vec3(0.8, 1.0, 0.8).mul(intensity.pow(4.0));
    const matrixColor = greenTail.add(whiteHead);

    return vec4(clamp(matrixColor, 0.0, 1.0), baseCol.a);
  })();
};
