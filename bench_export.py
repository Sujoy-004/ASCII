"""Benchmark runner for Render Free tier 512 MB RAM / 0.1 vCPU memory and timing constraints.

Simulates production transcoding of 1080p video under Render Free limits using psutil
to sample complete process tree RSS (Python parent + FFmpeg child subprocesses) at 50ms intervals.
Verifies peak RSS stays strictly below 250 MB and transcode duration < 75 seconds per D-07 and INFRA-04.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import NamedTuple

import psutil

from src.api.jobs import ExportJob
from src.api.transcode import run_ffmpeg_transcode


class BenchmarkResult(NamedTuple):
    duration_sec: float
    elapsed_sec: float
    peak_rss_mb: float
    format: str
    passed: bool
    details: str


class ProcessTreeMemorySampler:
    """Samples complete process tree RSS (parent + all recursive children) periodically."""

    def __init__(self, interval_sec: float = 0.050) -> None:
        self.interval_sec = interval_sec
        self.peak_rss_bytes: int = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._parent = psutil.Process(os.getpid())

    def _sample_loop(self) -> None:
        while not self._stop_event.is_set():
            total_rss = 0
            try:
                total_rss += self._parent.memory_info().rss
                for child in self._parent.children(recursive=True):
                    try:
                        total_rss += child.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            if total_rss > self.peak_rss_bytes:
                self.peak_rss_bytes = total_rss

            time.sleep(self.interval_sec)

    def start(self) -> None:
        self._stop_event.clear()
        self.peak_rss_bytes = self.current_rss_bytes()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> int:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        # Final sample check
        current = self.current_rss_bytes()
        if current > self.peak_rss_bytes:
            self.peak_rss_bytes = current
        return self.peak_rss_bytes

    def current_rss_bytes(self) -> int:
        total = 0
        try:
            total += self._parent.memory_info().rss
            for child in self._parent.children(recursive=True):
                try:
                    total += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return total


def generate_synthetic_webm(
    output_path: str,
    duration_sec: float = 30.0,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
) -> None:
    """Generate a synthetic 1080p WebM test video using FFmpeg lavfi testsrc."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg executable not found on system PATH.")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration_sec:.2f}:size={width}x{height}:rate={fps}",
        "-c:v",
        "libvpx",
        "-b:v",
        "500k",
        "-deadline",
        "realtime",
        "-cpu-used",
        "8",
        "-threads",
        "1",
        output_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to generate synthetic WebM video: {res.stderr}")


async def run_export_benchmark_async(
    duration_sec: float = 30.0,
    fps: int = 30,
    format: str = "mp4",
    threshold_rss_mb: float = 250.0,
    threshold_time_sec: float = 75.0,
    existing_input_path: str | None = None,
) -> BenchmarkResult:
    """Execute the full export benchmark and evaluate memory and timing limits asynchronously."""
    work_dir = tempfile.mkdtemp(prefix="ascii_bench_")
    sampler = ProcessTreeMemorySampler(interval_sec=0.050)

    try:
        input_webm = existing_input_path
        if not input_webm:
            input_webm = os.path.join(work_dir, "synthetic_input.webm")
            print(f"[*] Generating {duration_sec:.1f}s 1080p WebM synthetic source...")
            generate_synthetic_webm(
                output_path=input_webm,
                duration_sec=duration_sec,
                fps=fps,
                width=1920 if format != "gif" else 1280,
                height=1080 if format != "gif" else 720,
            )

        output_file = os.path.join(work_dir, f"output.{format}")
        now = time.time()
        job = ExportJob(
            id="bench_01",
            token_hash="bench_hash",
            format=format,
            duration=duration_sec,
            fps=fps,
            state="encoding",
            created_at=now,
            updated_at=now,
        )

        print(f"[*] Commencing transcode: format={format}, threads=1, preset=ultrafast...")
        sampler.start()
        start_time = time.perf_counter()

        # Run async transcode pipeline
        await run_ffmpeg_transcode(
            job=job,
            input_path=input_webm,
            output_path=output_file,
        )

        elapsed_sec = time.perf_counter() - start_time
        peak_bytes = sampler.stop()
        peak_rss_mb = peak_bytes / (1024 * 1024)

        rss_ok = peak_rss_mb <= threshold_rss_mb
        time_ok = elapsed_sec <= threshold_time_sec
        passed = rss_ok and time_ok

        details = (
            f"Peak RSS: {peak_rss_mb:.2f} MB (limit: {threshold_rss_mb:.1f} MB) - {'OK' if rss_ok else 'EXCEEDED'}\n"
            f"Elapsed: {elapsed_sec:.2f} s (limit: {threshold_time_sec:.1f} s) - {'OK' if time_ok else 'EXCEEDED'}"
        )

        return BenchmarkResult(
            duration_sec=duration_sec,
            elapsed_sec=elapsed_sec,
            peak_rss_mb=peak_rss_mb,
            format=format,
            passed=passed,
            details=details,
        )

    finally:
        sampler.stop()
        shutil.rmtree(work_dir, ignore_errors=True)


def run_export_benchmark(
    duration_sec: float = 30.0,
    fps: int = 30,
    format: str = "mp4",
    threshold_rss_mb: float = 250.0,
    threshold_time_sec: float = 75.0,
    existing_input_path: str | None = None,
) -> BenchmarkResult:
    """Synchronous wrapper for running export benchmark, handling nested event loops if present."""
    coro = run_export_benchmark_async(
        duration_sec=duration_sec,
        fps=fps,
        format=format,
        threshold_rss_mb=threshold_rss_mb,
        threshold_time_sec=threshold_time_sec,
        existing_input_path=existing_input_path,
    )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def print_report(res: BenchmarkResult) -> None:
    """Print structured terminal diagnostic summary table."""
    banner = "=" * 68
    print("\n" + banner)
    print("  RGB ASCII & RETRO FX STUDIO - RENDER FREE 512MB RAM BENCHMARK")
    print(banner)
    print(f"  Target Duration:        {res.duration_sec:.1f} seconds (1080p @ 30fps)")
    print(f"  Target Format:          {res.format.upper()} (-threads 1 -preset ultrafast)")
    print(f"  Elapsed Transcode Time: {res.elapsed_sec:.2f} seconds")
    print(f"  Peak Process Tree RSS:  {res.peak_rss_mb:.2f} MB")
    print("  Render Free RAM Limit:  512.00 MB (Safety Threshold: 250.00 MB)")
    print("  Max Time Threshold:     75.00 seconds")
    print("-" * 68)
    status_label = "[PASS] CONSTRAINTS SATISFIED" if res.passed else "[FAIL] CONSTRAINTS BREACHED"
    print(f"  Final Benchmark Status: {status_label}")
    print(banner + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Free 512MB RAM Export Benchmark")
    parser.add_argument("--duration", type=float, default=30.0, help="Test video duration in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Test video framerate")
    parser.add_argument("--format", type=str, default="mp4", choices=["mp4", "gif"], help="Output format")
    parser.add_argument("--quick", action="store_true", help="Quick mode (3-second clip) for CI validation")
    parser.add_argument("--rss-limit", type=float, default=250.0, help="Peak RSS threshold in MB")
    parser.add_argument("--time-limit", type=float, default=75.0, help="Max transcode time threshold in seconds")

    args = parser.parse_args()
    duration = 3.0 if args.quick else args.duration
    time_limit = 20.0 if args.quick else args.time_limit

    res = run_export_benchmark(
        duration_sec=duration,
        fps=args.fps,
        format=args.format,
        threshold_rss_mb=args.rss_limit,
        threshold_time_sec=time_limit,
    )
    print_report(res)
    return 0 if res.passed else 1


if __name__ == "__main__":
    sys.exit(main())
