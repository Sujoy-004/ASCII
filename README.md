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
timing — is detected and chosen automatically. **No flags are needed**: every
option below is a tweak for a specific situation, not a setup step.

---

## ◆ Features

- **Real-time RGB ASCII rendering** — video streams live into the terminal.
- **ANSI 24-bit True Color** — each character keeps its source pixel's color.
- **Region-faithful color sampling** — every character's color is the box/area
  average of the entire source region it covers (FFmpeg `flags=area` at decode,
  plus a dependency-free area-averaged resizer), so no single arbitrary pixel
  determines a cell's color and smooth gradients render without banding.
- **Experimental half-block color** (`RGB_ASCII_HALF_BLOCK=1`, opt-in) — renders
  each cell as the `▀` upper-half block with two stacked colors, doubling
  vertical color density without changing the visible grid size.
- **Simultaneous audio playback** through FFplay.
- **Automatic terminal-size adaptation** — the render grid fits your window and follows live resizes during playback.
- **Aspect-ratio preservation** — corrects for non-square terminal characters.
- **Audio-master playback timing** — when FFplay exposes its media clock, video deadlines follow the audio-derived playback position; a monotonic fallback remains available.
- **Real-time frame dropping** — stale frames are dropped to stay on track when the terminal can't keep up.
- **Adaptive quality** (on by default) — when the pipeline can't hold its frame budget, optional work is shed in a fixed order (temporal smoothing first, then color) instead of dropping frames. It never changes frame timing, frame selection, or audio sync, so playback stays smooth and synchronized; only detail is reduced. Turn it off with `--no-adaptive` when you want byte-identical output regardless of machine speed.
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

### Installation

Nothing is required to run it from a clone — the runtime is standard library
only, so `python -m src.main` works as-is. To get the `rgb-ascii` command and
the test suite on your `PATH`:

```bash
git clone https://github.com/Sujoy-004/ASCII.git
cd ASCII
python -m pip install -e ".[dev]"
rgb-ascii "assets/videos/test.mp4"     # same as python -m src.main
```

FFmpeg and FFplay are still external executables and must be on your `PATH` (see
Requirements).

### Options

There is one flag, because there is one thing worth overriding per run:

| Flag | Effect |
|------|--------|
| `--adaptive` / `--no-adaptive` | Force adaptive quality on or off. Omit it to use the default (on), or set `RGB_ASCII_NO_ADAPTIVE=1`. |

`--help` lists the full set of environment variables. The ones you are most
likely to reach for:

| Variable | Effect |
|----------|--------|
| `RGB_ASCII_NO_ADAPTIVE=1` | Disable adaptive quality (same as `--no-adaptive`). |
| `RGB_ASCII_HALF_BLOCK=1` | Double vertical color density with `▀` half-blocks. |
| `RGB_ASCII_NO_AUDIO=1` | Skip the audio track entirely. |

Environment values are read leniently: a numeric variable that cannot be read,
or an out-of-range value, falls back to the default rather than being fatal, so
a typo degrades instead of refusing to play. Booleans follow one rule — any
value other than `0`, `false`, `no` or `off` counts as "on". An explicit flag
always wins over the environment.

Half-block mode encodes two colors per cell, so it cannot be combined with
`RGB_ASCII_NO_COLOR`; that combination is rejected with a clear error instead of
failing mid-playback.

### Development

```bash
python -m pytest        # full suite; no FFmpeg or terminal required
python -m mypy          # type-check the package
python -m ruff check .  # lint (rule scope documented in pyproject.toml)
```

The test suite is fully hermetic — FFmpeg, FFplay and FFprobe are faked — so it
runs anywhere Python does, and the same commands run in CI on Linux and Windows
against Python 3.10 and 3.13.

### Benchmark

`bench.py` measures the render pipeline (smooth → resize → render → write) with
no FFmpeg, no terminal, and a fixed seed, so runs are comparable across
processes and machines:

```bash
python bench.py                                   # default grids
python bench.py --sizes 160x48                    # pure steady state (src == grid)
python bench.py --src 640x360                     # the terminal-resize path
python bench.py --json base.json                  # save
python bench.py --json base.json --baseline base.json   # before/after
```

The default source size (160×48) matches the largest default grid, so that row is
what the player actually does in steady state; the smaller default grids
(80×22, 120×38) also pay an area resize. Pass a `--src` equal to each grid to
measure pure steady-state playback. A before/after column is only printed when
both runs measured the same work; a baseline with a different source size, sink
or seed is refused rather than silently compared, and the run prints absolute
numbers with the reason.

### requirements.txt

`requirements.txt` lists **Python** package dependencies only. The runtime is
**standard library only** — it declares no third-party Python packages. FFmpeg
and FFplay are native executables and are **not** Python dependencies, so they
are documented here and in the install section rather than in
`requirements.txt`. (Pytest is kept as a development dependency.)

---

## ◆ How It Works

1. **FFmpeg** decodes the video into raw **RGB24** frames, scaling each frame
   to the terminal grid with **area averaging** (`scale=...:flags=area`) so a
   decoded pixel is the mean of the entire source region it covers.
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
   dependency-free box/area averaging (matching the decode-path sampling) and
   rendered at the new grid size.
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
│   ├── __init__.py     Package marker (modules import as `src.*`)
│   ├── main.py         CLI entry point and orchestration
│   ├── video.py        FFmpeg decoding
│   ├── renderer.py     RGB → luminance → ASCII, RGB → ANSI color
│   ├── terminal.py     Size detection, ANSI control, screen adaptation
│   ├── timing.py       Frame pacing toward absolute deadlines
│   ├── audio.py        FFplay playback, FFprobe audio detection
│   ├── sync.py         Shared playback timeline & completion policy
│   ├── framesel.py     Timeline-based frame selection & dropping
│   ├── smoothing.py    Optional temporal smoothing
│   ├── adaptive.py     Adaptive quality: utilization tracking & lever shedding
│   └── config.py       All tunable settings
├── tests/              pytest suite (hermetic; no FFmpeg needed)
├── assets/             Test media (assets/videos/test.mp4)
├── bench.py            Seeded render-pipeline benchmark
├── .github/workflows/  CI: compile, import, pytest, mypy, ruff, bench smoke
│                       on Linux/Windows × Python 3.10/3.13
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
**Adaptive quality** complements it: before frames start dropping, optional work
is shed so detail degrades instead of smoothness.

Measured with `python bench.py --sizes 160x48` (Python 3.11, Windows, steady
state where the source size equals the grid, so no resize happens; 30 FPS =
33.3 ms/frame budget). These are machine-specific — reproduce before trusting
them for your setup:

| Configuration (160×48 grid) | Cost per frame | Headroom vs. budget |
|-----------------------------|----------------|---------------------|
| Mono, no smoothing | ~2.2 ms | ~15× |
| Color, no smoothing | ~4.8 ms | ~7× |
| Half-block, no smoothing | ~10.5 ms | ~3× |
| Color, with smoothing | ~7.5 ms | ~4× |

Smoothing costs roughly 1–1.5 ms/frame at this size (it blends per decoded
source pixel, so it scales with the decoded frame rather than the grid).
Grid sizes smaller than the source add a resize; `--src 640x360` shows that
path deliberately. Run `python bench.py` for numbers on your own machine.

---

## ◆ Limitations

Accurately stated, not hidden:

- **True sample-accurate audio-device timestamps** are not exposed through the current FFplay subprocess integration. The synchronization clock uses FFplay's audio-master media position, which is materially better than process-launch timing but is not a device sample counter.
- **Terminal performance** depends heavily on the terminal emulator and its
  output throughput.
- **Dropped frames** are an intentional real-time tradeoff under load.

---

## ◆ Roadmap / Future Work

Not yet done, and genuinely open:

- Controlled PCM/audio-device playback if true sample-accurate device-clock
  synchronization is required (see Limitations).
- Configurable character gradients and resolution via CLI flags, rather than the
  environment variables used today.
- ASCII image-renderer mode and webcam/stream input.

Already implemented, and previously listed here: source-frame-timestamp
synchronization with automatic FPS detection (see How It Works, step 5) and
adaptive quality.

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
