---
last_mapped_commit: a55586b3cdf529951d93b522083233d43fa80a2e
last_mapped_at: 2026-11-16
---
# Testing Patterns

**Analysis Date:** 2026-11-16

## Test Framework

**Runner:**
- `pytest` (configured via `[tool.pytest.ini_options]` in `pyproject.toml`)
- Config: `pythonpath = ["."]`, `testpaths = ["tests"]`

**Assertion Library:**
- Standard Python `assert` statements enriched by pytest introspection.

**Run Commands:**
```bash
python -m pytest               # Run all 380+ tests
python -m pytest tests/test_sync.py  # Run a single test module
python -m pytest -k "test_deadline" # Run specific test cases by name
python -m pytest -q            # Quiet summary mode (used in CI)
```

## Test File Organization

**Location:**
- Dedicated `tests/` directory at the repository root. Tests are separate from source code (`src/`).

**Naming:**
- Files: `tests/test_<module_or_feature>.py`
- Test functions: `def test_<behavior_or_scenario>():`
- Test classes (when grouping): `class Test<Feature>:`

**Structure:**
```
tests/
├── test_adaptive.py           # Adaptive quality controller tests
├── test_audio.py              # Audio player lifecycle and stats parsing tests
├── test_bench.py              # Benchmark harness execution and JSON output tests
├── test_brightness.py         # Luminance formula and character lookup tests
├── test_cleanup.py            # Signal handling, process termination, cursor restore tests
├── test_cli.py                # Command line flags and env var parsing tests
├── test_frame_reader.py       # FFmpeg reader pipe, stderr, and decode error tests
├── test_framesel.py           # FrameSelector lag recovery and drop statistics tests
├── test_media_errors.py       # Fault injection for missing/corrupt media files
├── test_playback.py           # Full simulated playback loop integration tests
├── test_renderer.py           # ASCII output, ANSI True Color, and half-block tests
├── test_sampling.py           # Point sampling and area-averaging resizing tests
├── test_smoothing.py          # TemporalSmoother alpha blend tests
├── test_startup_sync.py       # Clock priming and media clock adoption tests
├── test_sync.py               # Timeline tracking, drift calculation, timeout tests
├── test_terminal.py           # Viewport dimensions and aspect ratio math tests
├── test_timestamp_stream.py   # Variable frame rate timestamp stream tests
├── test_timing.py             # FrameClock monotonic pacing and deadline tests
└── test_vfr_tail.py           # Pacing of final trailing frames in variable rate video
```

## Test Structure

**Suite Organization:**
Tests follow the standard Arrange-Act-Assert structure, using parameterization for matrix coverage:

```python
import pytest
from src.config import Config
from src.renderer import RGBAsciiRenderer

def test_renderer_monochrome_output():
    # Arrange
    config = Config(enable_color=False, chars=" #")
    renderer = RGBAsciiRenderer(config)
    # 2x1 image: black (0, 0, 0), white (255, 255, 255)
    frame = bytes([0, 0, 0, 255, 255, 255])

    # Act
    output = renderer.render_frame(frame, width=2, height=1)

    # Assert
    assert output == " #"
    assert "\x1b[" not in output
```

**Parameterized Testing Pattern:**
```python
@pytest.mark.parametrize(
    ("r", "g", "b", "expected_luminance"),
    [
        (0, 0, 0, 0),
        (255, 255, 255, 255),
        (255, 0, 0, 76),   # 0.299 * 255
        (0, 255, 0, 149),  # 0.587 * 255
        (0, 0, 255, 29),   # 0.114 * 255
    ],
)
def test_rec601_luminance(r: int, g: int, b: int, expected_luminance: int):
    assert luminance(r, g, b) == expected_luminance
```

## Mocking & Deterministic Test Doubles

**Duck-Typed Doubles over Uncontrolled Mocking:**
The test suite prefers small, deterministic test doubles rather than indiscriminate `unittest.mock.MagicMock` patches.

**Injectable Clocks and Sleep Callables:**
Components interacting with time (`FrameClock`, `AudioPlayer`, `PlaybackTimeline`) accept injected `now` and `sleep_fn` callables:
```python
current_time = 0.0

def fake_now():
    return current_time

def fake_sleep(seconds: float):
    nonlocal current_time
    current_time += seconds

clock = FrameClock(target_fps=30, now=fake_now, sleep_fn=fake_sleep)
```
This allows hundreds of seconds of virtual video playback to execute in microseconds deterministically without race conditions.

**Synthetic Frame Generators:**
- Tests construct deterministic pixel byte buffers (`bytes([r, g, b] * count)`).
- Mock frame readers implement the minimal reader protocol (`read_frame() -> bytes | None`, `width`, `height`, `frame_size`).

## Fixtures and Factories

**Test Fixtures:**
- Defined locally or per module to avoid global fixture pollution.
- Temporary files and directories are managed via pytest's standard `tmp_path` fixture.

## Coverage & Enforcement

**Current Test Metrics:**
- 387 passing tests covering unit logic, failure modes, race conditions, and CLI behaviors.
- Test execution time: ~9.5 seconds for the entire suite.
- Type check: `mypy` running with zero errors on `src/`.
- Linter: `ruff` clean on all checks.

## Test Types

**Unit Tests:**
- Isolated validation of pure functions and individual classes (`test_renderer.py`, `test_brightness.py`, `test_sampling.py`, `test_smoothing.py`).
- Exact mathematical verification of Rec. 601 weighting and box-averaging tiling.

**Timing & Scheduling Tests:**
- Simulates frame arrival, jitter, processing stalls, and verifies that `FrameSelector` drops stale frames accurately while `FrameClock` avoids drift accumulation (`test_timing.py`, `test_framesel.py`).

**Subprocess Failure & Recovery Tests:**
- Simulates missing binaries (`which` returning None), abnormal non-zero process exits, container errors, and partial streams (`test_frame_reader.py`, `test_media_errors.py`, `test_cleanup.py`).

**Integration Tests:**
- Tests running complete loops via `src.main.run` with mocked readers, verifying proper startup latency priming, A/V synchronization calculations, and end-of-stream timeouts (`test_playback.py`, `test_startup_sync.py`).

---

*Testing analysis: 2026-11-16*
