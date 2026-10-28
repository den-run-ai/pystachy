# pystachy: dynamic-any
"""Small repeated trace-repair workload; serialization is outside the timed loop.

Run with an iteration count (default 2000, ten records per iteration).
Compare the first output line and checksum across pristine/adapted/native runs
before comparing seconds. Zero iterations emits the exact output witness only.
"""
import json
import sys
from time import perf_counter
from typing import Any

from json_repair import repair_json


SOURCES: list[str] = [
    '{"role":"assistant","tool_calls":[{"id":"c1","name":"search","arguments":{"query":"redwoods","limit":3}}],"ok":true}',
    '{"role":"tool","call_id":"c1","items":[{"name":"trail","score":0.75},],"ok":true,}',
    "{role: 'assistant', ok: False, answer: None, retries: 2}",
    '```json\n{"step":3,"events":[{"type":"start"},{"type":"finish","ms":1.5}]}\n```',
    '{"step":4 "ok":true "payload":{"weights":[1,0.5,false,null]}}',
    '{"role":"assistant","code":"def f(x):\\n    return x + 1\\n","path":"src/main.py","ok":true}',
    '{"role":"assistant","code":"def f(x):\n    return x + 1\n","ok":true}',
    '{"name":"search","arguments":"{\\"query\\":\\"redwoods\\",}","ok":true}',
    '{"ok":fal',
    'Result:\n{"step":6,"ok":false,"events":[{"x":1},{"x":2}]}\nDone.',
]


def weight(value: Any) -> int:
    if not isinstance(value, dict):
        raise ValueError("benchmark expected an object")
    score = len(value) * 17
    verdict: Any = value.get("ok", None)
    if isinstance(verdict, bool):
        score += 3 if verdict else 5
    elif isinstance(verdict, str):
        score += len(verdict) * 7
    if "code" in value:
        score += len(value["code"])
    if "events" in value:
        score += len(value["events"])
    return score


rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
if rounds < 0:
    raise ValueError("iterations must be nonnegative")
outputs: list[Any] = []
per_round = 0
for source in SOURCES:
    result: Any = repair_json(source, return_objects=True)
    outputs.append(result)
    per_round += weight(result)
print("outputs", json.dumps(outputs, ensure_ascii=True, sort_keys=True))
print("per_round", per_round)

checksum = 0
start = perf_counter()
for _ in range(rounds):
    for source in SOURCES:
        checksum += weight(repair_json(source, return_objects=True))
seconds = perf_counter() - start
if checksum != rounds * per_round:
    raise ValueError("repair checksum changed across repeated calls")
print("records", rounds * len(SOURCES))
print("checksum", checksum)
print("seconds", seconds)
