<!-- generated-by: gsd-doc-writer -->
# Getting Started

This guide walks you through setting up **RGB ASCII & Retro FX Studio** on your local machine, running your first terminal video playback, and launching the interactive web studio.

---

## Prerequisites

Ensure you have the following runtimes and tools installed on your operating system:

| Dependency | Required Version | Verification Command | Description |
|------------|------------------|----------------------|-------------|
| **Python** | `>= 3.10` | `python --version` | Core rendering engine, CLI, and FastAPI backend. |
| **Node.js** | `>= 18.0.0` | `node --version` | React and Vite studio frontend runtime. |
| **FFmpeg** | Any recent build (`>= 4.4`) | `ffmpeg -version` | Video frame decoding and backend transcoding. |
| **FFplay** | Included with FFmpeg | `ffplay -version` | Audio playback stream for the terminal player. |

### Installing FFmpeg

- **macOS** (Homebrew):
  ```bash
  brew install ffmpeg
  ```
- **Ubuntu/Debian**:
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```
- **Windows** (winget or Chocolatey):
  ```powershell
  winget install Gyan.FFmpeg
  # or
  choco install ffmpeg
  ```

---

## Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Sujoy-004/ASCII.git
   cd ASCII
   ```

2. **Set up Python virtual environment and install core package:**
   ```bash
   python -m venv .venv

   # Activate virtual environment
   # On macOS/Linux:
   source .venv/bin/activate
   # On Windows (PowerShell):
   .venv\Scripts\Activate.ps1

   # Install the package and dependencies
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Install Web Studio dependencies:**
   ```bash
   cd web
   npm install
   cd ..
   ```

---

## First Run

### 1. Terminal Video Playback
Play an example video directly inside your ANSI True Color terminal:

```bash
rgb-ascii assets/videos/test.mp4
```

You should see real-time color ASCII characters flowing at 30 FPS with source audio playback through your speakers. Press `Ctrl+C` or wait for the video to finish to cleanly restore the terminal screen.

### 2. Local Web Studio
Launch the browser studio with live preview and WebGPU acceleration:

```bash
cd web
npm run dev
```

Navigate to `http://localhost:5173`. Drag and drop an image or video file into the stage to test real-time shader modes.

### 3. Local Export API Backend
Launch the FastAPI transcoding backend:

```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify service readiness by querying `http://127.0.0.1:8000/health`.

---

## Common Setup Issues

### 1. `FFmpegNotFoundError` or `FFplayNotFoundError`
- **Symptom**: CLI crashes immediately with an error stating `ffmpeg` or `ffplay` was not found on `PATH`.
- **Solution**: Confirm that `ffmpeg` and `ffplay` are in your system PATH by running `ffmpeg -version` and `ffplay -version` in a new shell window. If using Windows, restart your terminal after updating Environment Variables.

### 2. Color artifacts or garbled escape codes in terminal
- **Symptom**: Terminal prints raw ANSI sequences like `\033[38;2;...` instead of colored characters.
- **Solution**: Ensure you are using a modern terminal emulator supporting 24-bit True Color:
  - Windows: Windows Terminal (recommended), VS Code integrated terminal.
  - macOS: iTerm2, Kitty, Alacritty, or Terminal.app (macOS 13+).
  - Linux: GNOME Terminal, Kitty, Alacritty, WezTerm.
  - Force monochrome output if your terminal lacks 24-bit color: `rgb-ascii video.mp4 --no-color`.

### 3. Audio fails to play or hangs on start
- **Symptom**: Video does not advance or audio fails silently.
- **Solution**: Test FFplay independently on your audio drivers: `ffplay -nodisp -autoexit assets/videos/test.mp4`. Alternatively, bypass audio playback entirely: `rgb-ascii video.mp4 --no-audio`.

---

## Next Steps

- Explore development patterns and code conventions: [DEVELOPMENT.md](DEVELOPMENT.md)
- Learn how to run unit and integration tests: [TESTING.md](TESTING.md)
- Review system architecture and shader internals: [ARCHITECTURE.md](ARCHITECTURE.md)
- Inspect available CLI and API configuration options: [CONFIGURATION.md](CONFIGURATION.md)
