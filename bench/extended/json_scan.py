# pystachy: dynamic-any
"""Warmed JSON decoder / repair-facade scanning controls; no timing thresholds.

From the repository root (the repair facade is the maintained adapted port):
  PYTHONPATH=ports python3 bench/extended/json_scan.py direct long 8192 2000 3 7
  PYSTACHY_PATH=ports ./pystachy run bench/extended/json_scan.py repair sparse 8192 2000 3 7

Arguments: direct|repair, long|short|mixed|sparse|dense|unicode|control,
string size, calls per batch, warmup batches, measured batches. Use long sizes
4096, 8192 and 16384 for N/2N/4N. Short/mixed have fixed small inputs.

Suite form: suite all|no-direct-control BASE MULTIPLIER WARMUPS SAMPLES.
For example, suite all 4096 1 3 7 runs both APIs and all three long sizes in
one process, compiling JIT only once. Other cases use size 8192 and fixed batch
counts scaled by MULTIPLIER. Select no-direct-control for PyPy 8.0.1, whose
control-character error offset is one character earlier than CPython's; this
omits only that incompatible diagnostic case, keeping the oracle unchanged.

Setup and complete expected-value checks are outside timing. Every call's result
is consumed inside timing; the checksum is checked after every batch. The first
batch is reported separately. Compare process medians in interleaved, pinned
runs; compilation/startup and instrumented memory runs belong in separate records.
Both APIs are compiled into this driver, so its startup is not a decoder-only
startup measurement. Direct mode uses dynamic JSON, as the repair facade does.
"""
import json
import sys
from time import perf_counter_ns
from typing import Any

from json_repair import repair_json


def make_case(name: str, size: int) -> tuple[str, dict[str, Any], int]:
    value = ""
    encoded = ""
    error_pos = -1
    if name == "long":
        value = "x," * (size // 2) + "x" * (size % 2)
        encoded = value
    elif name == "short":
        value = "abcdefgh"
        encoded = value
    elif name == "mixed":
        expected: dict[str, Any] = {
            "a": "short", "n": 17, "ok": True, "empty": "", "items": [1, "two", None],
        }
        return '{"a":"short","n":17,"ok":true,"empty":"","items":[1,"two",null]}', expected, -1
    elif name == "sparse":
        # Ordinary spans occur before and after an escape, including a short tail.
        part = "x" * (size // 4)
        value = (part + "\n") * 4 + "tail"
        encoded = (part + "\\n") * 4 + "tail"
    elif name == "dense":
        value = "a\nb" * (size // 3) + "z" * (size % 3)
        encoded = "a\\nb" * (size // 3) + "z" * (size % 3)
    elif name == "unicode":
        value = "é中😀a" * (size // 4) + "é" * (size % 4)
        encoded = value
    elif name == "control":
        # Direct JSON rejects this exact byte; repair preserves it in the value.
        value = "x" * (size - 1) + chr(1)
        encoded = value
        error_pos = 6 + size - 1
    else:
        raise ValueError("unknown workload")
    expected_value: dict[str, Any] = {"a": value}
    return '{"a":"' + encoded + '"}', expected_value, error_pos


def validate(mode: str, source: str, expected: dict[str, Any], error_pos: int) -> None:
    if mode == "direct" and error_pos >= 0:
        try:
            json.loads(source)
        except json.JSONDecodeError as exc:
            assert exc.msg == "Invalid control character at"
            assert exc.pos == error_pos and exc.lineno == 1 and exc.colno == error_pos + 1
            return
        raise AssertionError("malformed control input was accepted")
    value: Any = json.loads(source) if mode == "direct" else repair_json(source, return_objects=True)
    assert value == expected


def batch(mode: str, source: str, count: int, error_pos: int) -> int:
    checksum = 0
    if mode == "repair":
        for i in range(count):
            value: Any = repair_json(source, return_objects=True)
            checksum += len(value["a"])
    elif error_pos < 0:
        for i in range(count):
            decoded: Any = json.loads(source)
            checksum += len(decoded["a"])
    else:
        for i in range(count):
            try:
                json.loads(source)
            except json.JSONDecodeError as exc:
                checksum += exc.pos
    return checksum


def run_case(mode: str, name: str, size: int, count: int, warmups: int, samples: int) -> None:
    if mode not in ["direct", "repair"] or size < 1 or count < 1 or warmups < 0 or samples < 1:
        raise ValueError("invalid benchmark arguments")
    source, expected, error_pos = make_case(name, size)
    validate(mode, source, expected, error_pos)
    per_call: int = error_pos if mode == "direct" and error_pos >= 0 else len(expected["a"])
    expected_checksum = count * per_call
    print("case", mode, name, size, len(source), len(source.encode()), count)
    start = perf_counter_ns()
    first = batch(mode, source, count, error_pos)
    elapsed = perf_counter_ns() - start
    assert first == expected_checksum
    print("first", first, elapsed)
    for i in range(warmups):
        checksum = batch(mode, source, count, error_pos)
        assert checksum == expected_checksum
        print("warmup", checksum)
    for i in range(samples):
        start = perf_counter_ns()
        checksum = batch(mode, source, count, error_pos)
        elapsed = perf_counter_ns() - start
        assert checksum == expected_checksum
        print("sample", checksum, elapsed)
    validate(mode, source, expected, error_pos)
    print("verified", per_call)


def suite(selection: str, base: int, multiplier: int, warmups: int, samples: int) -> None:
    if selection not in ["all", "no-direct-control"] or base < 1 or multiplier < 1 or warmups < 0 or samples < 1:
        raise ValueError("invalid suite arguments")
    cases: list[tuple[str, int]] = [
        ("short", 200000), ("mixed", 40000), ("sparse", 3000),
        ("dense", 300), ("unicode", 300), ("control", 300),
    ]
    for mode in ["direct", "repair"]:
        for factor in [1, 2, 4]:
            run_case(mode, "long", base * factor, multiplier * 2000, warmups, samples)
        for name, calls in cases:
            if name == "control" and mode == "direct" and selection == "no-direct-control":
                continue
            if name == "control" and mode == "repair":
                calls = 100
            run_case(mode, name, 8192, multiplier * calls, warmups, samples)


def main() -> None:
    if len(sys.argv) != 7:
        raise ValueError("expected: direct|repair CASE SIZE CALLS WARMUPS SAMPLES, or suite SELECTION BASE MULTIPLIER WARMUPS SAMPLES")
    if sys.argv[1] == "suite":
        suite(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))
    else:
        run_case(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))


main()
