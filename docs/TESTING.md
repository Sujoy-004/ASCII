<!-- generated-by: gsd-doc-writer -->
# Testing Guide

This document describes the testing framework, test suite organization, mocking conventions, and execution procedures for **RGB ASCII & Retro FX Studio**.

---

## Test Framework and Setup

The project uses **pytest** (`>= 7.0`) for Python test discovery, parameterized assertions, and fixture injection. Tests are fully hermetic and do not require external FFmpeg binaries or network connections during execution: all media feeds and subprocess outputs are exercised using synthetic byte streams and protocol mocks.

### Dependencies

```bash
pip install pytest pytest-asyncio pytest-cov
```

Test configuration is declared in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

---

## Running Tests

### 1. Full Python Test Suite

Execute the entire test suite of 435 unit and integration tests:

```bash
pytest tests/
```

Run in quiet mode with summary:

```bash
pytest tests/ -q
```

### 2. Running Targeted Tests

Run a specific test module:

```bash
pytest tests/test_renderer.py -v
pytest tests/test_api_transcode.py -v
pytest tests/test_framesel.py -v
```

Filter by test function name:

```bash
pytest -k "test_rebase_to_audio_clock"
```

### 3. Frontend Validation

Verify the TypeScript web studio codebase:

```bash
cd web
npm run build
```

This executes `tsc --noEmit` to ensure strict type compatibility, followed by Vite production bundling.

---

## Writing New Tests

### Test File Conventions
- Store all Python test files in `tests/` prefixed with `test_` matching the subsystem under test (e.g., `tests/test_api_security.py`).
- Use descriptive snake_case test function names stating expected behavior: `test_quality_controller_sheds_smoothing_on_sustained_lag`.

### Mocking Guidelines & Synthetic Buffers
- **No Disk I/O or Subprocess Leaks**: Do not spawn real FFmpeg processes in unit tests. Use mock pipes, in-memory buffers (`io.BytesIO`), or duck-typed sinks.
- **Protocol Conformance**: Modules like `FrameClock`, `TimestampSource`, and `TerminalRenderer` use Python `Protocol` or abstract interfaces for clean dependency injection.
- **Example Unit Test Pattern**:

```python
from src.config import Config
from src.renderer import RGBAsciiRenderer


def test_renderer_luminance_mapping():
    cfg = Config(chars=" .#", enable_color=False)
    renderer = RGBAsciiRenderer(cfg)

    # Black pixel (0, 0, 0) maps to darkest char " "
    black_rgb = bytes([0, 0, 0])
    char_black = renderer.render_pixel_monochrome(black_rgb)
    assert char_black == " "

    # White pixel (255, 255, 255) maps to brightest char "#"
    white_rgb = bytes([255, 255, 255])
    char_white = renderer.render_pixel_monochrome(white_rgb)
    assert char_white == "#"
```

---

## Coverage & Benchmark Tests

### Coverage Reports
Generate a terminal test coverage breakdown:

```bash
pytest --cov=src tests/
```

### Performance Benchmarks
Two standalone benchmark harnesses are included for throughput testing:

```bash
# Terminal renderer frame scaling benchmark
python bench.py

# Server-side transcode pipeline benchmark
python bench_export.py
```

---

## CI Integration

No CI/CD pipeline is currently configured in the repository (`.github/workflows/` is not present). Tests should be executed locally prior to submitting pull requests or deploying changes:

```bash
python -m pytest tests/ -q && npm --prefix web run build
```
