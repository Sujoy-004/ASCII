"""Smoke tests for bench.py.

The benchmark is the project's only performance evidence, so the things that
make it trustworthy -- reproducible output bytes, and refusing to compare two
runs that measured different work -- are worth pinning down. Everything here
uses the smallest possible grid and one pass, so the whole file runs in well
under a second and needs no FFmpeg and no terminal.
"""

import json

import pytest

import bench

TINY = ["8x4"]


@pytest.fixture(autouse=True)
def _restore_source_globals():
    """bench.main() rebinds module-level SRC_WIDTH/SRC_HEIGHT from --src, which
    would otherwise leak one test's source size into the next one's default."""
    saved = (bench.SRC_WIDTH, bench.SRC_HEIGHT)
    yield
    bench.SRC_WIDTH, bench.SRC_HEIGHT = saved


def _row(stdout: str) -> dict:
    """Parse the 'bytes/frm' cell back out of the printed table."""
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) == 10 and parts[0].startswith("8x4/"):
            return {"id": parts[0], "fps": float(parts[6]), "bytes": parts[7]}
    raise AssertionError(f"no 8x4 row in output:\n{stdout}")


def test_smoke_runs_and_exits_zero(capsys):
    assert bench.main(["--repeat", "1", "--sizes", ",".join(TINY)]) == 0
    out = capsys.readouterr().out
    assert "bench: src" in out
    assert _row(out)["bytes"].replace(",", "").isdigit()


def test_output_bytes_independent_of_repeat(capsys):
    """The regression this guards: bytes/frm used to be sampled from whichever
    pass won on wall clock, so a stateful (smoothing) row changed with --repeat
    -- a timing race deciding a value that depends on a logical call count."""
    bench.main(["--repeat", "1", "--sizes", ",".join(TINY)])
    first = _row(capsys.readouterr().out)["bytes"]
    bench.main(["--repeat", "3", "--sizes", ",".join(TINY)])
    second = _row(capsys.readouterr().out)["bytes"]
    assert first == second


def test_json_payload_carries_comparability_metadata(tmp_path, capsys):
    out_file = tmp_path / "r.json"
    assert bench.main(["--repeat", "1", "--sizes", ",".join(TINY), "--src", "8x4",
                       "--json", str(out_file)]) == 0
    capsys.readouterr()
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["meta"]["src"] == "8x4"
    assert payload["meta"]["sink"] == "null"
    assert payload["meta"]["seed"] == bench.SEED
    assert [r["id"] for r in payload["results"]]


def test_incomparable_baseline_is_rejected_not_compared(tmp_path, capsys):
    """A 640x360-source baseline and a 8x4-source run measured different work
    (one resizes every frame, the other does not). Reporting a percentage
    between them invents a speedup that does not exist, so the run must fall
    back to absolute numbers only and say why."""
    out_file = tmp_path / "r.json"
    bench.main(["--repeat", "1", "--sizes", ",".join(TINY), "--json", str(out_file)])
    capsys.readouterr()

    assert bench.main(["--repeat", "1", "--sizes", ",".join(TINY), "--src", "16x8",
                       "--baseline", str(out_file)]) == 0
    err = capsys.readouterr().err
    assert "measured different work" in err
    assert "src:" in err


def test_comparable_baseline_is_accepted(tmp_path, capsys):
    out_file = tmp_path / "r.json"
    bench.main(["--repeat", "1", "--sizes", ",".join(TINY), "--json", str(out_file)])
    capsys.readouterr()
    assert bench.main(["--repeat", "1", "--sizes", ",".join(TINY),
                       "--baseline", str(out_file)]) == 0
    captured = capsys.readouterr()
    assert "measured different work" not in captured.err
    # Same id, so the row is compared rather than reported as new.
    assert _row(captured.out)["id"].endswith("smooth_off")
    assert "%" in captured.out
    assert " new " not in captured.out


@pytest.mark.parametrize("payload", ["not json at all", "[]", "{}", '{"results": {}}'])
def test_unusable_baseline_degrades_to_absolute_only(tmp_path, capsys, payload):
    """Previously a list-shaped or results-less JSON raised inside the
    comprehension and killed the whole run; the bench should still print
    numbers when the baseline is simply unusable."""
    bad = tmp_path / "bad.json"
    bad.write_text(payload, encoding="utf-8")
    assert bench.main(["--repeat", "1", "--sizes", ",".join(TINY), "--baseline", str(bad)]) == 0
    assert "absolute numbers only" in capsys.readouterr().err
