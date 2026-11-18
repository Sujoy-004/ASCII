import {
  Fn,
  uv,
  texture,
  vec2,
  vec4,
  floor,
  fract,
  clamp,
} from 'three/tsl';

export interface AsciiNodeInputs {
  sourceNode: any; // sampled media/upstream color node (vec4)
  atlasTexture: any; // texture node for the character atlas
  cellScale: any; // cell size in px (uniform)
  charSpacing: any; // [0, 8] px cell padding (uniform, SHADER-01)
  charAspect: any; // width/height ratio (uniform, default 0.5)
  rampLength: any; // number of characters in atlas (uniform)
  resolution: any; // [canvasWidth, canvasHeight] (uniform)
}

/**
 * Parameterized ASCII shader node using TSL (SHADER-01).
 * Quantizes UVs according to cellScale, charAspect (0.5), and charSpacing padding.
 * Maps cell color to Rec. 601 perceived luminance (0.299*R + 0.587*G + 0.114*B),
 * samples the character glyph from the horizontal strip atlas, and modulates with RGB.
 */
export const asciiShaderNode = (inputs: AsciiNodeInputs) => {
  const {
    sourceNode,
    atlasTexture,
    cellScale,
    charSpacing,
    charAspect,
    rampLength,
    resolution,
  } = inputs;

  return Fn(() => {
    const st = uv();

    // Cell size in normalized UV coordinates
    const pixelCoord = st.mul(resolution);
    const cellW = cellScale.mul(charAspect).max(1.0);
    const cellH = cellScale.max(1.0);
    const cellSize = vec2(cellW, cellH);

    // Discrete cell anchor coordinates
    const cellIndex = floor(pixelCoord.div(cellSize));
    const cellCenterPx = cellIndex.mul(cellSize).add(cellSize.mul(0.5));
    const cellCenterUV = cellCenterPx.div(resolution);

    // Sample color
    const sampledColor = typeof sourceNode === 'function' ? sourceNode(cellCenterUV) : sourceNode;
    const rgb = sampledColor.rgb;

    // Rec. 601 perceived luminance (0.299*R + 0.587*G + 0.114*B) - matches src/renderer.py:49-51
    const lum = rgb.r.mul(0.299).add(rgb.g.mul(0.587)).add(rgb.b.mul(0.114));

    // Character index in horizontal atlas strip [0, rampLength - 1]
    const maxIdx = rampLength.sub(1.0).max(0.0);
    const charIdx = floor(lum.mul(maxIdx.add(0.999))).clamp(0.0, maxIdx);

    // Normalized UV position inside the cell [0, 1]
    const cellUV = fract(pixelCoord.div(cellSize));

    // Normalized cell padding p = charSpacing / cellSize
    // innerUV = clamp((cellUV - p) / (1.0 - 2.0 * p), 0.0, 1.0)
    const padNorm = charSpacing.div(cellSize).min(0.45); // prevent divide by zero
    const innerUV = clamp(
      cellUV.sub(padNorm).div(vec2(1.0).sub(padNorm.mul(2.0))),
      0.0,
      1.0
    );

    // Map innerUV to sub-region of horizontal atlas strip
    // x offset = (charIdx + innerUV.x) / rampLength
    const atlasUV = vec2(charIdx.add(innerUV.x).div(rampLength), innerUV.y);

    // Sample glyph coverage from character atlas (monochrome alpha in red channel)
    const glyphMask = texture(atlasTexture, atlasUV).r;

    // Modulate media color with character glyph mask for TrueColor output
    const finalRGB = rgb.mul(glyphMask);

    return vec4(finalRGB, sampledColor.a);
  })();
};
