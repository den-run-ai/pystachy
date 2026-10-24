# pystachy: dynamic-any
# times tomllib.loads() of a 526 KB document of 3,000 mixed records, excluding start-up and I/O
import sys
import time
import tomllib
from typing import Any


def checksum(doc: Any) -> str:
    ints = 0
    floats = 0.0
    strs = 0
    tags = 0
    dates = 0
    for r in doc["records"]:
        a = r["amount"]
        if isinstance(a, bool):
            pass
        elif isinstance(a, int):
            ints += a
        elif isinstance(a, float):
            floats += a
        else:
            strs += 1
        tags += len(r["tags"])
        if "when" in r:
            dates += 1
        floats += r["meta"]["score"] + r["point"]["y"]
    return f"{len(doc['records'])} {ints} {floats:.3f} {strs} {tags} {dates}"


def main() -> None:
    with open(sys.argv[1]) as f:
        text = f.read()
    rounds = int(sys.argv[2])
    times: list[int] = []
    doc: Any = None
    for _ in range(rounds):
        t0 = time.perf_counter_ns()
        doc = tomllib.loads(text)
        times.append(time.perf_counter_ns() - t0)
    times.sort()
    print(checksum(doc))
    print(f"median {times[len(times) // 2] / 1e6:.1f} ms min {times[0] / 1e6:.1f} ms")


main()
