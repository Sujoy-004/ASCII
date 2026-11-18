# Changelog

All notable changes to **RGB ASCII & Retro FX Studio** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-18

### Added
- **Web Studio (WebGPU / TSL)**: Real-time interactive browser studio with 16 hardware retro shaders (ASCII glyph atlas, Floyd-Steinberg and Bayer dithering, halftone screen printing, matrix rain, VHS/CRT scanlines, directional pixel sorting, blockify, and Rec. 601 tone grading).
- **Responsive Layout**: Multi-viewport layout with collapsible side rails and overlay drawers for mobile devices (< 768px).
- **Client & Server Export**: Client-side lossless PNG, JPEG, animated GIF, ASCII text, SVG, and WebM capture; FastAPI backend transcoding pipeline for high-fidelity MP4 and GIF exports.
- **Python Terminal Player**: Zero-dependency standard library Python CLI delivering 24-bit ANSI True Color playback with FFmpeg pipe decoding, monotonic clock pacing, and adaptive load shedding.
- **Continuous Integration**: GitHub Actions multi-OS (Ubuntu, Windows) test matrix across Python 3.10 and 3.13, paired with automated web bundle build verification and Dependabot security updates.
- **Issue & PR Templates**: Structured YAML forms for bug reporting, feature proposals, and pull request reviews.
