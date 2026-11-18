<!-- generated-by: gsd-doc-writer -->
# RGB ASCII & Retro FX Studio

Real-time retro visual effects and ASCII studio for images, videos, and live webcam streams across browser, headless API, and terminal interfaces.

[![CI](https://github.com/Sujoy-004/ASCII/actions/workflows/ci.yml/badge.svg)](https://github.com/Sujoy-004/ASCII/actions/workflows/ci.yml)
[![Live Studio](https://img.shields.io/badge/Live%20Studio-rgb--ascii.pages.dev-00f0ff?style=for-the-badge&logo=cloudflarepages&logoColor=black)](https://rgb-ascii.pages.dev)
[![Python Version](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![WebGPU](https://img.shields.io/badge/WebGPU-Three.js%20TSL-990000?style=for-the-badge&logo=webgpu&logoColor=white)](https://threejs.org/)

---

## Overview

**RGB ASCII & Retro FX Studio** transforms digital media into stylized retro computer graphics. It pairs a zero-install WebGPU browser studio with a standard-library Python terminal player and a high-performance FastAPI/FFmpeg export service.

- **Browser Studio**: Interactive WebGPU/TSL canvas featuring 16 real-time retro shaders (ASCII glyph atlas, Floyd-Steinberg and Bayer dithering, halftone dot screens, matrix digital rain, VHS/CRT scanlines, directional pixel sorting, blockify, and Rec. 601 pre-tone controls).
- **Terminal Player**: Python CLI delivering 24-bit ANSI True Color playback directly in modern terminals, synchronized with FFplay audio streaming and adaptive frame rate load shedding.
- **Export Backend**: Production FastAPI microservice running bounded FFmpeg transcoding pipelines to render and download full-resolution MP4 clips and animated GIFs.

🌐 **Try the Live Studio:** [https://rgb-ascii.pages.dev](https://rgb-ascii.pages.dev)

### Quick Start (One Command)

Run the interactive browser studio locally with zero backend dependencies:

```bash
git clone https://github.com/Sujoy-004/ASCII.git && cd ASCII/web && npm install && npm run dev
```

---

## Installation

### Prerequisites

- **Python**: `>= 3.10`
- **Node.js**: `>= 18.0.0` (for web development or local frontend builds)
- **FFmpeg & FFplay**: Required on system `PATH` for video decoding and audio playback in the terminal CLI and export backend.

### Python Package & CLI

Install the core package and CLI entry point locally:

```bash
# Clone the repository
git clone https://github.com/Sujoy-004/ASCII.git
cd ASCII

# Install in editable mode
pip install -e .
```

To run the test suite and development tools, install development dependencies:

```bash
pip install -r requirements.txt
```

### Web Frontend Studio

```bash
cd web
npm install
```

---

## Quick Start

### 1. Launch the Terminal Video Player

Play any video file directly in your ANSI 24-bit True Color terminal:

```bash
# Using the console entrypoint
rgb-ascii path/to/video.mp4

# Or run directly as a module
python -m src.main path/to/video.mp4
```

### 2. Run the Local Web Studio

Start the Vite development server with hot module reloading:

```bash
cd web
npm run dev
```

Open `http://localhost:5173` in any modern browser supporting WebGPU or WebGL2.

### 3. Start the Export API Service

Run the FastAPI backend with Uvicorn:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check endpoint: `http://localhost:8000/health`.

---

## Usage Examples

### Terminal CLI Options

```bash
# Play video with double vertical color density using upper-half block characters (▀)
rgb-ascii input.mp4 --half-block

# Use dense 70-character luminance ramp without audio playback
rgb-ascii input.mp4 --preset dense --no-audio

# Disable ANSI True Color escapes for high-contrast monochrome ASCII
rgb-ascii input.mp4 --no-color

# Enable temporal alpha smoothing (0.2 blend toward incoming frames)
rgb-ascii input.mp4 --smoothing 0.2

# Custom ASCII character ramp (darkest to brightest)
rgb-ascii input.mp4 --chars " .:*#@"
```

### Web Studio Features

1. **Load Media**: Drag and drop images (`PNG`, `JPG`, `WebP`, `GIF`) or videos (`MP4`, `WebM`), or stream live video from your webcam.
2. **Apply Shaders**: Switch between 16 primary shader modes on the left rail (`ascii`, `dither`, `halftone`, `vhs`, `matrix`, `dots`, `pixelSort`, `blockify`, etc.).
3. **Tune Parameters**: Adjust cell size, screen angles, matrix speed, color glitches, and Rec. 601 pre-tone curves (brightness, contrast, saturation, gamma, invert).
4. **Export Results**:
   - Client-side: Lossless PNG, JPEG, animated GIF (up to 5s), WebM recording, raw ASCII text, or vector SVG.
   - Server-side: High-resolution MP4 video and animated GIF transcoding with source audio track preservation.

---

## Architecture & Documentation

Comprehensive architectural blueprints and operator guides are located in the `docs/` directory:

- [System Architecture](docs/ARCHITECTURE.md)
- [Getting Started Guide](docs/GETTING-STARTED.md)
- [Development Workflow](docs/DEVELOPMENT.md)
- [Testing Guide](docs/TESTING.md)
- [Configuration Reference](docs/CONFIGURATION.md)
- [API Reference](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
