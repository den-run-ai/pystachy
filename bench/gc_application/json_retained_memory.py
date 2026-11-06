"""Retained JSON consumer with embedded input and complete deterministic stdout.

smoke|full ROUNDS WINDOW. Generate gc_json_fixture.py with embed_fixture.py and
add its directory plus bench to the import path. This is a separate workload
from json_retained.py: a static source literal removes managed input allocation
and file I/O. The parse/rollup/retained-window operations remain the same.
"""
from __future__ import annotations

import json
import sys

from gc_json_fixture import FULL, SMALL
from json_records import process


def main() -> None:
    mode = sys.argv[1]
    if mode != "smoke" and mode != "full":
        raise ValueError("mode must be smoke or full")
    source = SMALL if mode == "smoke" else FULL
    rounds = int(sys.argv[2])
    window = int(sys.argv[3])
    if rounds < 1 or window < 1:
        raise ValueError("rounds and window must be positive")
    retained: list[json.JSONValue] = []
    total = 0
    per_batch = 0
    records = 0
    for iteration in range(rounds):
        value = json.loads(source)
        if not isinstance(value, list):
            raise ValueError("expected a JSON array")
        score = process(value, False)
        if iteration == 0:
            per_batch = score
            records = len(value)
        elif score != per_batch or len(value) != records:
            raise ValueError("batch rollup changed")
        total += score
        if len(retained) < window:
            retained.append(value)
        else:
            retained[iteration % window] = value
    retained_score = 0
    for value in retained:
        retained_score += process(value, False)
    if retained_score != per_batch * len(retained):
        raise ValueError("retained batch rollup changed")
    last = retained[(rounds - 1) % window]
    encoded = json.dumps(last)
    print("ingested_records", rounds * records)
    print("rollup", total)
    print("retained_batches", len(retained))
    print("retained_rollup", retained_score)
    print("output_chars", len(encoded))
    print("output", encoded)


if __name__ == "__main__":
    main()
