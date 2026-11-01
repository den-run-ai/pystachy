# pystachy: dynamic-any
"""Common-workload repair facade probe with exact per-input witnesses.

MODE ROUNDS [BATCHES WARMUPS]. MODE is valid, malformed, serialized-valid or
serialized-malformed. Four inputs per round; no wide ints or changed comment
cases. Timed work retains each latest result and accumulates its length.
ROUNDS=0 permits whole-process startup observations including validation.
"""
import json
import sys
from time import perf_counter
from typing import Any

from json_repair import repair_json


EXPECTED: list[str] = [
    '{"id": 1, "name": "alpha", "ok": true, "items": [1, 2, 3]}',
    '{"id": 2, "name": "beta", "ok": false, "items": [4, 5]}',
    '{"id": 3, "name": "gamma", "ok": true, "items": [6, null]}',
    '{"id": 4, "name": "line\\nend", "ok": true, "items": [7, 8]}',
]
MALFORMED: list[str] = [
    "{id: 1, name: 'alpha', ok: True, items: [1,2,3,],}",
    '{"id":2 "name":"beta" "ok":false "items":[4,5]}',
    '```json\n{"id":3,"name":"gamma","ok":true,"items":[6,null]}\n```',
    '{"id":4,"name":"line\nend","ok":true,"items":[7,8],}',
]


def validate(results: list[Any], serialized: bool) -> None:
    if len(results) != len(EXPECTED):
        raise ValueError("wrong number of repaired results")
    for index in range(len(EXPECTED)):
        output: Any = results[index] if serialized else json.dumps(results[index], ensure_ascii=True)
        if not isinstance(output, str) or output != EXPECTED[index]:
            raise ValueError("complete repaired result differs from the explicit expected output")


mode = sys.argv[1] if len(sys.argv) > 1 else "malformed"
rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 200
batches = int(sys.argv[3]) if len(sys.argv) > 3 else 1
warmups = int(sys.argv[4]) if len(sys.argv) > 4 else 0
if mode not in ("valid", "malformed", "serialized-valid", "serialized-malformed"):
    raise ValueError("expected valid, malformed, serialized-valid or serialized-malformed")
if rounds < 0 or batches < 1 or warmups < 0:
    raise ValueError("rounds/warmups must be nonnegative, batches positive")
serialized = mode.startswith("serialized-")
sources = MALFORMED if mode.endswith("malformed") else EXPECTED
results: list[Any] = []
per_round = 0
for source in sources:
    result: Any = repair_json(source, return_objects=not serialized)
    results.append(result)
    per_round += len(result)
validate(results, serialized)
# Explicit expected strings are small; retaining them makes the witness replayable.
print("outputs", json.dumps(EXPECTED))
print("witness before", mode, len(sources), per_round, "exact")
print("rounds", rounds)

for batch in range(warmups + batches):
    checksum = 0
    start = perf_counter()
    for _ in range(rounds):
        for index in range(len(sources)):
            result = repair_json(sources[index], return_objects=not serialized)
            results[index] = result
            checksum += len(result)
    elapsed = perf_counter() - start
    if checksum != rounds * per_round:
        raise ValueError("iteration checksum changed")
    validate(results, serialized)
    print("witness after", batch, mode, len(results), checksum, "exact")
    print("warmup_seconds" if batch < warmups else "seconds", elapsed)
