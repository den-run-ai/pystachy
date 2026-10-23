# pystachy: dynamic-any
# Pystachy port: boxed heterogeneous JSON values use the opt-in runtime.
from typing import Any
import time

import json
import sys

# Pystachy port: pyperf is not imported; the deterministic main below times its function.


# Pystachy port: explicitly type the empty document and its heterogeneous workload tuple.
EMPTY_DATA: dict[str, Any] = {}
EMPTY: tuple[Any, int] = (EMPTY_DATA, 2000)
SIMPLE_DATA = {'key1': 0, 'key2': True, 'key3': 'value', 'key4': 'foo',
               'key5': 'string'}
SIMPLE = (SIMPLE_DATA, 1000)
NESTED_DATA = {'key1': 0, 'key2': SIMPLE[0], 'key3': 'value', 'key4': SIMPLE[0],
               'key5': SIMPLE[0], 'key': '\u0105\u0107\u017c'}
NESTED = (NESTED_DATA, 1000)
HUGE = ([NESTED[0]] * 1000, 1)

CASES = ['EMPTY', 'SIMPLE', 'NESTED', 'HUGE']


# Pystachy port: retain typed range iteration around boxed document payloads.
def bench_json_dumps(data: list[tuple[Any, range]]) -> None:
    for obj, count_it in data:
        for _ in count_it:
            json.dumps(obj)


# Pystachy port: a deterministic main replaces pyperf.Runner.
# Keep upstream payloads/counts by default; smoke reduces counts and HUGE length.
# Validate complete encoded results outside the timed calls, rather than their length alone.
if __name__ == "__main__":
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    smoke = len(sys.argv) > 2 and sys.argv[2] == "smoke"
    huge: Any = [NESTED_DATA] * (3 if smoke else 1000)
    cases: list[tuple[Any, int]] = [EMPTY, SIMPLE, NESTED, (huge, 1)]
    data: list[tuple[Any, range]] = [(obj, range(1 if smoke else count)) for obj, count in cases]
    t0 = time.perf_counter()
    for _ in range(loops):
        bench_json_dumps(data)
    print("seconds", time.perf_counter() - t0, file=sys.stderr)
    print("json_dumps", loops)
    for obj, count in [EMPTY, SIMPLE, NESTED]:
        print(json.dumps(obj))
    encoded = json.dumps(huge)
    assert encoded == "[" + ", ".join([json.dumps(NESTED_DATA)] * len(huge)) + "]"
    print("huge", len(huge), len(encoded))
