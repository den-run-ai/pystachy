"""Ingest JSON batches, calculate a rollup, and keep a bounded recent-batch cache.

PATH ROUNDS WINDOW OUTPUT. The input and processing logic come from the existing
JSON consumer benchmark. The last page is encoded in full to OUTPUT so the
controller can compare its bytes with CPython. All stdout is deterministic.
"""
from __future__ import annotations

import json
import sys

from json_records import process


def main() -> None:
    path = sys.argv[1]
    rounds = int(sys.argv[2])
    window = int(sys.argv[3])
    if rounds < 1 or window < 1:
        raise ValueError("rounds and window must be positive")
    with open(path) as stream:
        source = stream.read()
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
    # Read the old pages after allocation/collection pressure, so a collector
    # must preserve every reachable field, tag and uncommon amount alternative.
    retained_score = 0
    for value in retained:
        retained_score += process(value, False)
    if retained_score != per_batch * len(retained):
        raise ValueError("retained batch rollup changed")
    last = retained[(rounds - 1) % window]
    encoded = json.dumps(last)
    with open(sys.argv[4], "w") as stream:
        stream.write(encoded)
        stream.write("\n")
    print("ingested_records", rounds * records)
    print("rollup", total)
    print("retained_batches", len(retained))
    print("retained_rollup", retained_score)
    print("output_chars", len(encoded))


if __name__ == "__main__":
    main()
