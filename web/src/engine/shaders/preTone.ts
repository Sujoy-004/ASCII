import {
  Fn,
  vec3,
  vec4,
  clamp,
  pow,
  mix,
} from 'three/tsl';

export interface PreToneInputs {
  colorNode: any; // vec4 input color node
  brightness: any; // uniform float (0..2, default 1)
  contrast: any; // uniform float (0..2, default 1)
  saturation: any; // uniform float (0..2, default 1)
  hueRotation: any; // uniform float in [-180, 180] degrees (SHADER-03)
  gamma: any; // uniform float (0.1..3, default 1)
  invert: any; // uniform float or int (0 = off, 1 = on)
}

/**
 * Pre-Tone shader node using TSL (SHADER-03, D-06 stage 1).
 * Executes real-time color adjustments before the primary effect:
 * 1. Brightness offset: (brightness - 1.0)
 * 2. Contrast: (rgb - 0.5) * contrast + 0.5
 * 3. Saturation: blend with Rec. 601 grayscale
 * 4. Hue rotation: Rodrigues rotation matrix around diagonal axis (1, 1, 1)/sqrt(3)
 * 5. Gamma correction: pow(clamp(rgb, 0.0, 1.0), vec3(1.0 / gamma))
 * 6. Invert: mix(rgb, 1.0 - rgb, invert)
 */
export const preToneNode = (inputs: PreToneInputs) => {
  const {
    colorNode,
    brightness,
    contrast,
    saturation,
    hueRotation,
    gamma,
    invert,
  } = inputs;

  return Fn(() => {
    const col = colorNode;
    let rgb = col.rgb;

    // 1. Brightness: tone.brightness is in [0, 2], neutral = 1.0
    // Offset is brightness - 1.0
    rgb = rgb.add(brightness.sub(1.0));

    // 2. Contrast: tone.contrast in [0, 2], neutral = 1.0
    // (rgb - 0.5) * contrast + 0.5
    rgb = rgb.sub(0.5).mul(contrast).add(0.5);

    // 3. Saturation: blend between Rec. 601 luminance and color
    const lum = rgb.r.mul(0.299).add(rgb.g.mul(0.587)).add(rgb.b.mul(0.114));
    const gray = vec3(lum);
    rgb = mix(gray, rgb, saturation);

    // 4. Hue Rotation: hueRotation in [-180, 180] degrees
    // Rodrigues' rotation formula around axis k = (1, 1, 1)/sqrt(3):
    // v_rot = v * cos(theta) + (k x v) * sin(theta) + k * (k . v) * (1 - cos(theta))
    // angle in radians = hueRotation * (PI / 180) = hueRotation * 0.017453292519943295
    const angle = hueRotation.mul(0.017453292519943295);
    const cosA = angle.cos();
    const sinA = angle.sin();
    const oneMinusCos = cosA.oneMinus();

    // k = vec3(1.0 / sqrt(3.0)) ~= vec3(0.577350269)
    const k = vec3(0.5773502691896258);
    const kCrossRgb = k.cross(rgb);
    const kDotRgb = k.dot(rgb);

    const hueRotated = rgb
      .mul(cosA)
      .add(kCrossRgb.mul(sinA))
      .add(k.mul(kDotRgb).mul(oneMinusCos));

    rgb = clamp(hueRotated, 0.0, 1.0);

    // 5. Gamma correction: pow(clamp(rgb, 0.0, 1.0), vec3(1.0 / gamma))
    const invGamma = gamma.reciprocal();
    rgb = pow(rgb.clamp(0.0001, 1.0), vec3(invGamma));

    // 6. Invert toggle
    const invertedRgb = vec3(1.0).sub(rgb);
    rgb = mix(rgb, invertedRgb, invert);

    return vec4(rgb, col.a);
  })();
};
