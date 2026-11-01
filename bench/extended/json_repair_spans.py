# pystachy: dynamic-any
"""Exact-output controls for repair-string spans; no timing thresholds.

From the repository root, using the maintained adapted port in both engines:
  PYTHONPATH=ports python3.13 bench/extended/json_repair_spans.py objects long 4096 100 3 7
  PYSTACHY_PATH=ports ./pystachy run bench/extended/json_repair_spans.py serialize sparse 4096 100 3 7

Arguments: objects|serialize, short|mixed|long|sparse|dense|unicode|punctuation|regex,
target value size, rounds per batch, warmup batches, measured batches. One round
repairs every input in the case (five inputs for mixed, otherwise one). Short and
mixed have fixed small inputs. Use sizes 4096, 8192 and 16384 for N/2N/4N controls.

Every call sets skip_json_loads=True to isolate repair from the valid JSON decoder.
Long/plain and punctuation inputs contain a raw newline and trailing object comma;
escaped cases also have a trailing comma. Thus the large strings cannot take the
repair parser's simple-quoted-string shortcut. Short/mixed retain small fast paths.

Complete expected values, code points and serialized text are checked before and
after timing. Each timed result contributes to a checked checksum. The first batch
is separate; use interleaved pinned process medians and record startup, compilation,
memory and source/toolchain identity separately. The mixed inputs are synthetic
controls, not a production distribution or complete compatibility evaluation.
"""
import json
import sys
from time import perf_counter_ns
from typing import Any

from json_repair import repair_json


def sized_text(unit: str, size: int) -> str:
    # Preserve whole punctuation/regex units; the remainder is ordinary text.
    return unit * (size // len(unit)) + "x" * (size % len(unit))


def make_case(name: str, size: int) -> tuple[list[str], list[dict[str, Any]]]:
    if name == "mixed":
        sources = [
            '{"a":"short","n":17}',
            "{a: 'words'}",
            '{"a":"line\\nnext",}',
            '{"a":"é中😀","ok":true,}',
            '{"a":"ends here}',
        ]
        expected: list[dict[str, Any]] = [
            {"a": "short", "n": 17},
            {"a": "words"},
            {"a": "line\nnext"},
            {"a": "é中😀", "ok": True},
            {"a": "ends here"},
        ]
        return sources, expected
    value = ""
    encoded = ""
    if name == "short":
        value = "a\nb"
        encoded = "a\\nb"
    elif name == "long":
        value = sized_text("ordinary text ", size) + "\nend"
        encoded = value
    elif name == "sparse":
        part = sized_text("ordinary words ", size // 4)
        value = (part + "\n") * 4 + "tail"
        encoded = (part + "\\n") * 4 + "tail"
    elif name == "dense":
        value = "x\n" * (size // 2) + "x" * (size % 2) + "end"
        encoded = "x\\n" * (size // 2) + "x" * (size % 2) + "end"
    elif name == "unicode":
        part = sized_text("é中😀a ", size)
        value = part + "\nend"
        encoded = part + "\\nend"
    elif name == "punctuation":
        value = sized_text("left {abc} [xyz] (p) : end ", size) + "\nend"
        encoded = value
    elif name == "regex":
        value = sized_text('[ab"cd] ', size) + "\nend"
        encoded = value
    else:
        raise ValueError("unknown workload")
    result: dict[str, Any] = {"a": value}
    return ['{"a":"' + encoded + '",}'], [result]


def validate(sources: list[str], expected: list[dict[str, Any]], serialized: list[str]) -> None:
    assert len(sources) == len(expected) and len(expected) == len(serialized)
    for i in range(len(sources)):
        value: Any = repair_json(sources[i], return_objects=True, skip_json_loads=True)
        assert isinstance(value, dict) and value == expected[i]
        actual_text: str = value["a"]
        expected_text: str = expected[i]["a"]
        assert len(actual_text) == len(expected_text)
        # Code-point comparison makes the Unicode witness explicit rather than
        # relying on an escaped JSON representation that can hide surrogate pairs.
        for j in range(len(expected_text)):
            assert ord(actual_text[j]) == ord(expected_text[j])
        assert repair_json(sources[i], skip_json_loads=True) == serialized[i]


def batch(mode: str, sources: list[str], rounds: int) -> int:
    checksum = 0
    if mode == "objects":
        for i in range(rounds):
            for source in sources:
                value: Any = repair_json(source, return_objects=True, skip_json_loads=True)
                checksum += len(value["a"])
    else:
        for i in range(rounds):
            for source in sources:
                text: Any = repair_json(source, skip_json_loads=True)
                checksum += len(text)
    return checksum


def run_case(mode: str, name: str, size: int, rounds: int, warmups: int, samples: int) -> None:
    if mode not in ["objects", "serialize"] or size < 1 or rounds < 1 or warmups < 0 or samples < 1:
        raise ValueError("invalid benchmark arguments")
    sources, expected = make_case(name, size)
    serialized: list[str] = [json.dumps(value) for value in expected]
    validate(sources, expected, serialized)
    per_round = 0
    source_chars = 0
    source_bytes = 0
    for i in range(len(sources)):
        per_round += len(expected[i]["a"]) if mode == "objects" else len(serialized[i])
        source_chars += len(sources[i])
        source_bytes += len(sources[i].encode())
    expected_checksum = rounds * per_round
    print("case", mode, name, size, source_chars, source_bytes, rounds * len(sources))
    start = perf_counter_ns()
    checksum = batch(mode, sources, rounds)
    elapsed = perf_counter_ns() - start
    assert checksum == expected_checksum
    print("first", checksum, elapsed)
    for i in range(warmups):
        checksum = batch(mode, sources, rounds)
        assert checksum == expected_checksum
        print("warmup", checksum)
    for i in range(samples):
        start = perf_counter_ns()
        checksum = batch(mode, sources, rounds)
        elapsed = perf_counter_ns() - start
        assert checksum == expected_checksum
        print("sample", checksum, elapsed)
    validate(sources, expected, serialized)
    print("verified", per_round)


def main() -> None:
    if len(sys.argv) != 7:
        raise ValueError("expected: objects|serialize CASE SIZE ROUNDS WARMUPS SAMPLES")
    run_case(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))


main()
