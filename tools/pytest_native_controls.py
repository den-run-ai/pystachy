"""Qualify deliberately failing tests against pytest, generated Python and native code.

Each execution runs the same 30-case suite. Four seeded success/failure pairs
exercise aliases, Unicode, numeric boundaries and exceptions. A runtime input
file supplies the seed offset, so native compilation cannot precompute the inputs.
Cleanup controls prove both teardown errors and subsequent fixture cleanup, and
strict XPASS must remain a failure. The qualification command exits zero only
when the *known failing* suite has its exact expected case and phase inventory.
"""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import sys

import pytest_native as runner

ROOT = Path(__file__).resolve().parents[1]
SEED_IDS = ("zero", "one", "large")
SOURCE = '''import math
import pytest

cleanup_events: list[str] = []

@pytest.fixture
def salt() -> int:
    with open("seed.txt") as source:
        return int(source.read())

@pytest.fixture
def values(salt: int) -> list[int]:
    return [salt]

@pytest.fixture
def alias(values: list[int]) -> list[int]:
    return values

@pytest.mark.parametrize("seed", [0, 1, 1729], ids=["zero", "one", "large"])
def test_alias_ok(seed: int, salt: int, values: list[int], alias: list[int]):
    assert alias is values
    alias.append(seed ^ salt)
    assert values == [salt, seed ^ salt]

@pytest.mark.parametrize("seed", [0, 1, 1729], ids=["zero", "one", "large"])
def test_alias_wrong(seed: int, salt: int, values: list[int], alias: list[int]):
    alias.append(seed ^ salt)
    assert values == [salt, (seed ^ salt) + 1]

def unicode_value(seed: int, salt: int) -> str:
    alphabet = ["é", "e\\u0301", "☃", "𐐀", "🙂", "\\x00"]
    return alphabet[(seed ^ salt) % len(alphabet)]

@pytest.mark.parametrize("seed", [0, 1, 1729], ids=["zero", "one", "large"])
def test_unicode_ok(seed: int, salt: int):
    value = unicode_value(seed, salt)
    text = "界" + value + "Я"
    assert text[1:-1] == value
    assert len(text) == len(value) + 2
    assert text.encode("utf-8").decode("utf-8") == text

@pytest.mark.parametrize("seed", [0, 1, 1729], ids=["zero", "one", "large"])
def test_unicode_wrong(seed: int, salt: int):
    value = unicode_value(seed, salt)
    assert ("界" + value + "Я")[1:-1] == value + "!"

@pytest.mark.parametrize("seed", [0, 1, 1729], ids=["zero", "one", "large"])
def test_numeric_ok(seed: int, salt: int):
    shift = (seed ^ salt) % 257
    high = 9223372036854775807 - shift
    low = -9223372036854775807 - 1 + shift
    assert high + shift == 9223372036854775807
    assert low - shift == -9223372036854775807 - 1
    assert (-shift) // 3 == -(shift // 3) - int(shift % 3 != 0)
    exact = 9007199254740991 + (shift & 1)
    assert int(float(exact)) == exact
    assert math.isnan(float("nan"))
    assert math.isinf(float("inf"))
    assert math.copysign(1.0, -float(shift - shift)) == -1.0

@pytest.mark.parametrize("seed", [0, 1, 1729], ids=["zero", "one", "large"])
def test_numeric_wrong(seed: int, salt: int):
    shift = (seed ^ salt) % 257
    high = 9223372036854775807 - shift
    assert high + shift == 9223372036854775806

def raise_value(value: int):
    raise ValueError("control:" + str(value))

@pytest.mark.parametrize("seed", [0, 1, 1729], ids=["zero", "one", "large"])
def test_exception_ok(seed: int, salt: int):
    with pytest.raises(ValueError, match="control:"):
        raise_value(seed ^ salt)

@pytest.mark.parametrize("seed", [0, 1, 1729], ids=["zero", "one", "large"])
def test_exception_wrong(seed: int, salt: int):
    with pytest.raises(ValueError, match="wrong:"):
        raise_value(seed ^ salt)

@pytest.fixture
def clean_first():
    cleanup_events.append("first setup")
    yield 1
    cleanup_events.append("first cleanup")

@pytest.fixture
def clean_second(clean_first: int):
    cleanup_events.append("second setup")
    yield clean_first
    cleanup_events.append("second cleanup")

def test_cleanup_ok(clean_second: int):
    assert clean_second == 1

def test_cleanup_ok_seen():
    assert cleanup_events == ["first setup", "second setup", "second cleanup", "first cleanup"]

@pytest.fixture
def bad_first():
    cleanup_events.append("bad first setup")
    yield 1
    cleanup_events.append("bad first cleanup")
    raise ValueError("first cleanup failed")

@pytest.fixture
def bad_second(bad_first: int):
    cleanup_events.append("bad second setup")
    yield bad_first
    cleanup_events.append("bad second cleanup")
    raise RuntimeError("second cleanup failed")

def test_cleanup_wrong(bad_second: int):
    assert bad_second == 1

def test_cleanup_wrong_seen():
    assert cleanup_events == ["first setup", "second setup", "second cleanup", "first cleanup",
                              "bad first setup", "bad second setup", "bad second cleanup", "bad first cleanup"]

@pytest.mark.xfail(reason="known assertion failure", strict=True)
def test_strict_expected_failure():
    assert False

@pytest.mark.xfail(reason="deliberate strict XPASS", strict=True)
def test_strict_unexpected_pass():
    assert True
'''


def expected_cases():
    """Keep the acceptance inventory independent of collection and generation."""
    names = []
    for category in ("alias", "unicode", "numeric", "exception"):
        for outcome in ("ok", "wrong"):
            names.extend(f"test_{category}_{outcome}[{seed}]" for seed in SEED_IDS)
    names.extend(("test_cleanup_ok", "test_cleanup_ok_seen", "test_cleanup_wrong",
                  "test_cleanup_wrong_seen", "test_strict_expected_failure", "test_strict_unexpected_pass"))
    return ["test_controls.py::" + name for name in names]


def expected_events():
    events = []
    for nodeid in expected_cases():
        for phase in ("setup", "call", "teardown"):
            outcome = "passed"
            if phase == "call":
                if "_wrong[" in nodeid or nodeid.endswith("test_strict_unexpected_pass"):
                    outcome = "failed"
                elif nodeid.endswith("test_strict_expected_failure"):
                    outcome = "xfailed"
            if phase == "teardown" and nodeid.endswith("test_cleanup_wrong"):
                outcome = "failed"
            events.append((nodeid, phase, outcome))
    return events


def phase_keys(events):
    return [(event["nodeid"], event["phase"],
             "failed" if event["outcome"] == "error" else event["outcome"]) for event in events]


def validate(results, oracle):
    if "error" in oracle:
        raise ValueError("pytest oracle failed: " + oracle["error"])
    if oracle.get("exit_code") != 1:
        raise ValueError("deliberately failing pytest suite must exit 1")
    if oracle.get("cases") != expected_cases() or phase_keys(oracle.get("events", [])) != expected_events():
        raise ValueError("pytest oracle differs from the independent control inventory")
    if len(results) != 1 or results[0].state != "test-failed" or results[0].exit_code != 1:
        raise ValueError("generated control suite must complete with test failures and exit 1")
    if results[0].cases != expected_cases() or phase_keys(results[0].events) != expected_events():
        raise ValueError("generated control suite lost, reordered or changed a control outcome")
    differences = runner.compare(results, oracle)
    if differences:
        raise ValueError("; ".join(differences))


@contextmanager
def controlled_environment():
    # Import paths or disabled assertions must not let two equally misconfigured
    # executions certify controls. Preserve toolchain/GC flags for explicit runs.
    keys = ("PYTHONPATH", "PYSTACHY_PATH", "PYTHONHOME", "PYTHONOPTIMIZE")
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in previous.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)


def qualify(work, modes, compiler, python, timeout, input_seed):
    root = work / "inputs"
    path = root / "test_controls.py"
    runner.write_changed(path, SOURCE)
    seed_text = str(input_seed) + "\n"
    runner.write_changed(root / "seed.txt", seed_text)
    rows = []
    with controlled_environment():
        oracle = runner.oracle([path], root, work / "oracle", python, timeout)
        for mode in modes:
            results = runner.run_suite([path], root, work / mode, mode, compiler, python, timeout)
            row = {"mode": mode, "state": "error", "results": [asdict(result) for result in results]}
            try:
                validate(results, oracle)
                row["state"] = "matched"
            except (ValueError, KeyError, TypeError) as error:
                row["error"] = str(error)
            rows.append(row)
    return {"source_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(),
            "input_seed": input_seed, "input_sha256": hashlib.sha256(seed_text.encode()).hexdigest(),
            "cases": expected_cases(), "expected_events": expected_events(),
            "excluded_cases": [], "oracle": oracle, "results": rows,
            "state": "matched" if all(row["state"] == "matched" for row in rows) else "error"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", action="append", choices=("python", "jit", "aot"))
    parser.add_argument("--compiler", default=shlex.join([sys.executable, str(ROOT / "pystachy.py")]))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build/pytest-controls")
    parser.add_argument("--input-seed", type=int, default=104729)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    modes = args.mode or ["python", "jit", "aot"]
    if len(modes) != len(set(modes)):
        parser.error("modes must be unique")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be positive and finite")
    if not 0 <= args.input_seed <= 2147483647:
        parser.error("input seed must fit an unsigned 31-bit integer")
    work = args.work_dir.resolve()
    try:
        with runner.lock_work_directory(work):
            evidence = qualify(work, modes, shlex.split(args.compiler), args.python, args.timeout, args.input_seed)
            if args.json:
                runner.write_changed(args.json.resolve(), json.dumps(evidence, indent=2) + "\n")
            for row in evidence["results"]:
                print(f"controls/{row['mode']}: {row['state']} ({len(evidence['cases'])} cases)")
                if row["state"] != "matched":
                    print(row.get("error", ""), file=sys.stderr)
                    for result in row["results"]:
                        if result.get("error") or result.get("stderr"):
                            print(result.get("error", "") + "\n" + result.get("stderr", ""), file=sys.stderr)
            return int(evidence["state"] != "matched")
    except (OSError, ValueError) as error:
        print(f"controls error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
