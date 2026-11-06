# pystachy: dynamic-any
"""Normalize mixed JSON trace records using the adapted json_repair PyPI port.

INPUT_JSONL ROUNDS. Each input line is a JSON-encoded source string. Every record
is repaired to objects and serialized as normalized JSON. The final complete
batch and a consumed byte-count checksum are deterministic CPython witnesses.
"""
import json
import sys
from typing import Any

from json_repair import repair_json


def normalize(source: str) -> str:
    value: Any = repair_json(source, return_objects=True)
    if not isinstance(value, dict):
        raise ValueError("expected a repaired trace object")
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def main() -> None:
    rounds = int(sys.argv[2])
    if rounds < 1:
        raise ValueError("rounds must be positive")
    sources: list[str] = []
    with open(sys.argv[1]) as stream:
        for line in stream:
            source: Any = json.loads(line)
            if not isinstance(source, str):
                raise ValueError("expected JSON-encoded source strings")
            sources.append(source)
    if not sources:
        raise ValueError("expected at least one trace record")
    expected: list[str] = []
    per_round = 0
    for source in sources:
        encoded = normalize(source)
        expected.append(encoded)
        per_round += len(encoded)
    output: list[str] = []
    total = 0
    for _ in range(rounds):
        output = []
        for source in sources:
            encoded = normalize(source)
            output.append(encoded)
            total += len(encoded)
    if output != expected or total != rounds * per_round:
        raise ValueError("normalized records changed")
    print("outputs", json.dumps(output, ensure_ascii=True))
    print("records", rounds * len(sources))
    print("normalized_chars", total)


if __name__ == "__main__":
    main()
