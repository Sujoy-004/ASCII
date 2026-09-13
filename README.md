<div align="center">

# ◆ RGB ASCII Video Renderer

**A real-time terminal video player that converts RGB video frames into
colored ASCII art using Python, FFmpeg, and ANSI True Color — while playing
the source audio alongside.**

<sub>Python · FFmpeg · ANSI 24-bit True Color · Standard-Library Only</sub>

<a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-212529?style=for-the-badge&logo=python&logoColor=white"></a>
<a href="https://ffmpeg.org/"><img src="https://img.shields.io/badge/FFmpeg-343A40?style=for-the-badge&logo=ffmpeg&logoColor=white"></a>
<a href="https://ffmpeg.org/"><img src="https://img.shields.io/badge/FFplay-Audio-495057?style=for-the-badge&logo=ffmpeg&logoColor=white"></a>
<a href="https://github.com/Sujoy-004/ASCII"><img src="https://img.shields.io/badge/ANSI%20True%20Color-7A838D?style=for-the-badge&logo=terminal&logoColor=white"></a>

<sub>in: local video file — out: live colored ASCII in your terminal</sub>

</div>

---

## ◆ What It Is

Feed a local video file to a single command, and the terminal becomes the
screen: every pixel is turned into a character whose **luminance selects the
glyph** and whose **original RGB color becomes an ANSI 24-bit foreground
color**, while the source audio plays through FFplay at the same time.

```
          input.mp4
             │
   ┌─────────┴─────────┐
   │                   │
   ▼                   ▼
 FFmpeg              FFplay
   │                   │
 RGB frames           Audio
   │                   │
   ▼                   ▼
Frame timeline       Speakers
   │
   ▼
Temporal smoothing
   │
   ▼
RGB → luminance → ASCII
   │
   ▼
ANSI True Color
   │
   ▼
     Terminal
```

Everything — terminal size, video dimensions, aspect ratio, audio, color, and
timing — is detected and chosen automatically. **No flags are needed.**

---

## ◆ Features

- **Real-time RGB ASCII rendering** — video streams live into the terminal.
- **ANSI 24-bit True Color** — each character keeps its source pixel's color.
- **Simultaneous audio playback** through FFplay.
- **Automatic terminal-size adaptation** — the render grid fits your window and follows live resizes during playback.
- **Aspect-ratio preservation** — corrects for non-square terminal characters.
- **Audio-master playback timing** — when FFplay exposes its media clock, video deadlines follow the audio-derived playback position; a monotonic fallback remains available.
- **Real-time frame dropping** — stale frames are dropped to stay on track when the terminal can't keep up.
- **Optional temporal smoothing** blends displayed frames for a smoother look.
- **Arbitrary local video paths** — relative, absolute, or with spaces; no copying needed.
- **Standard-library Python** — no third-party Python packages at runtime.
- **Clean process & terminal cleanup** — terminal state and A/V processes are always restored, even on `Ctrl+C`.

---

## ◆ Demo

Below is a manually drawn illustration of the monochrome glyph layer. In actual
playback each character is **colored by ANSI True Color** from its source
pixel, so the output is far richer than this grayscale mockup:

```text
        ..+++*#%%%%#+++..                ..+++*#%%%%#+++..
    ..++*%#**+====+**#%*++..          ..++*%#**+====+**#%*++..
   .+*#*+=--::..::--=+*#*+.          .+*#*+=--::..::--=+*#*+.
   +#*=-:....  ......:-=*#+          +#*=-:....  ......:-=*#+
  *#*=-.              .-=*#*        *#*=-.              .-=*#*
 *%#=:.                .:=#%*      *%#=:.                .:=#%*
 @%=-:                  :-=%@      @%=-:                  :-=%@
 @%=:.       ...        .:=%@      @%=:.       ...        .:=%@
 @%=-:      ::=+=::      :-=%@     @%=-:      ::=+=::      :-=%@
 *%#=:.     .:-=*+:.     .:=#%*    *%#=:.     .:-=*+:.     .:=#%*
  *#*=-.      .:::      .-=*#*      *#*=-.      .:::      .-=*#*
   +#*=-:....  ....  ....:-=*#+      +#*=-:....  ....  ....:-=*#+
   .+*#*+=--:::....:::--=+*#*+.      .+*#*+=--:::....:::--=+*#*+.
    ..++*%#**+=====+**#%*++..        ..++*%#**+=====+**#%*++..
       ..=+++*#%%%%#*+++=..            ..=+++*#%%%%#*+++=..
```

> Run it for yourself with the bundled clip:
> `python -m src.main "assets/videos/test.mp4"`

---

## ◆ Requirements

**Python** (>= 3.10, standard library only) plus two **external native**
executables that **`requirements.txt` cannot install** — they must be present
on your `PATH`:

| Dependency | Required for | Notes |
|------------|--------------|-------|
| **FFmpeg** | Decoding the video into RGB frames | Video-only playback |
| **FFplay** | Playing the audio track | Included in most FFmpeg builds |

There is **no GitHub or network runtime dependency** — everything runs locally.

### Install FFmpeg + FFplay

- **Windows** — download a static build (e.g. from
  https://www.gyan.dev/ffmpeg/builds/, which bundles FFplay), extract it, and
  add the `bin\` folder to your system `PATH`.
- **macOS** — `brew install ffmpeg`
- **Linux** — `sudo apt install ffmpeg`

Then open a **new terminal window** (an old one keeps the prior `PATH`) and verify:

```bash
ffmpeg -version
ffplay -version
```

---

## ◆ Usage

One command. The video can be anywhere on your machine — no need to copy it
into this project:

```bash
python -m src.main "PATH_TO_VIDEO"
```

Examples:

```bash
# Windows
python -m src.main "C:\Users\You\Videos\movie.mp4"

# Linux / macOS
python -m src.main "/home/user/Videos/movie.mp4"

# Bundled test clip
python -m src.main "assets/videos/test.mp4"
```

- **Absolute paths** work.
- **Relative paths** work.
- **Paths containing spaces** work (the path is one argument).
- `Ctrl+C` stops playback cleanly and restores your terminal.

### requirements.txt

`requirements.txt` lists **Python** package dependencies only. The runtime is
**standard library only** — it declares no third-party Python packages. FFmpeg
and FFplay are native executables and are **not** Python dependencies, so they
are documented here and in the install section rather than in
`requirements.txt`. (Pytest is kept as a development dependency.)

---

## ◆ How It Works

1. **FFmpeg** decodes the video into raw **RGB24** frames.
2. **Python** renders each frame into an ANSI-colored ASCII string.
3. **Luminance** selects the glyph — computed with Rec. 601 weights:
   `Y = 0.299R + 0.587G + 0.114B`.
4. **RGB** becomes the ANSI **True Color** foreground:
   `ESC[38;2;R;G;Bm`.
5. A **FrameClock** schedules presentation against source frame timestamps when FFprobe can provide them, with fixed-FPS deadlines as a fallback.
6. **Stale frames are dropped** when playback falls behind the active media timeline.
7. Optional **temporal smoothing** blends displayed frames.
8. **FFplay** plays the source audio on a separate process and emits its current audio-master media position; video follows that clock when available.
9. When the terminal size changes, the current RGB frame is resized with
   dependency-free nearest-neighbor sampling and rendered at the new grid size.
10. The **terminal** redraws each frame in place, without scrolling.

### Technical Notes

- **RGB24** — 3 bytes per pixel (R, G, B), row-major.
- **Luminance** — Rec. 601 weights favor green, matching human perception.
- **ANSI True Color** — `\x1b[38;2;R;G;Bm` sets the foreground color; every
  pixel's color is carried into its character.
- **Frame timing** — source frame PTS values drive media deadlines when available; fixed-FPS timing is the fallback. The wall-clock deadline remains derived from one monotonic playback start.
- **Frame dropping** — an intentional real-time tradeoff under load, keeping
  playback near the current timeline instead of slowing down.
- **Process separation** — FFmpeg (video), FFplay (audio), and Python are
  separate processes coordinated by a video timeline that can follow FFplay's
  audio-derived media clock.

---

## ◆ Project Structure

```
ASCII/
├── src/
│   ├── main.py        CLI entry point and orchestration
│   ├── video.py       FFmpeg decoding
│   ├── renderer.py    RGB → luminance → ASCII, RGB → ANSI color
│   ├── terminal.py    Size detection, ANSI control, screen adaptation
│   ├── timing.py      Frame pacing toward absolute deadlines
│   ├── audio.py       FFplay playback, FFprobe audio detection
│   ├── sync.py        Shared playback timeline & completion policy
│   ├── framesel.py    Timeline-based frame selection & dropping
│   ├── smoothing.py   Optional temporal smoothing
│   └── config.py      All tunable settings
├── tests/             pytest suite
├── assets/            Test media (assets/videos/test.mp4)
├── README.md
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

---

## ◆ Performance

Terminal **output throughput can become the bottleneck**, especially at higher
resolutions and with ANSI True Color (each pixel emits a color sequence). Larger
terminals generate far more per-frame output, so the achievable frame rate
depends heavily on your terminal emulator.

**Frame dropping** keeps playback near the current timeline when the terminal
can't keep up — a deliberate real-time tradeoff rather than a slowdown.

---

## ◆ Limitations

Accurately stated, not hidden:

- **True sample-accurate audio-device timestamps** are not exposed through the current FFplay subprocess integration. The synchronization clock uses FFplay's audio-master media position, which is materially better than process-launch timing but is not a device sample counter.
- **Terminal performance** depends heavily on the terminal emulator and its
  output throughput.
- **Dropped frames** are an intentional real-time tradeoff under load.

---

## ◆ Roadmap / Future Work

- Controlled PCM/audio-device playback if true sample-accurate device-clock synchronization is required.
- Configurable character gradients and resolution via CLI flags.
- Frame-timestamp synchronization and automatic FPS detection.
- ASCII image-renderer mode and webcam/stream input.

---

## ◆ Reference & Credits

This project's concept is inspired by
**[RipperdocNiladri/ASCII-Art](https://github.com/RipperdocNiladri/ASCII-Art)**,
a collection of real-time ASCII rendering experiments. Our implementation is
an independent, purpose-built video renderer focused on a single polished
workflow — it shares the general idea of turning RGB frames into colored
terminal characters, but is not a fork or copy of that codebase.

---

<div align="center">

## ◆ RGB ASCII Video Renderer

<sub>Real-time colored ASCII video in your terminal, powered by Python, FFmpeg, and ANSI True Color.</sub>

<br>

<a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-212529?style=for-the-badge&logo=python&logoColor=white"></a>
<a href="https://ffmpeg.org/"><img src="https://img.shields.io/badge/FFmpeg-343A40?style=for-the-badge&logo=ffmpeg&logoColor=white"></a>
<a href="https://ffmpeg.org/"><img src="https://img.shields.io/badge/FFplay-495057?style=for-the-badge&logo=ffmpeg&logoColor=white"></a>
<a href="https://github.com/Sujoy-004/ASCII"><img src="https://img.shields.io/badge/MIT%20License-7A838D?style=for-the-badge&logo=github&logoColor=white"></a>

</div>

---

## ◆ License

MIT
