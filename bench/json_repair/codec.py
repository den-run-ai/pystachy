# pystachy: dynamic-any
"""Direct Any JSON probe without importing the promoting json_repair parser.

MODE ROWS ROUNDS [BATCHES WARMUPS]; MODE is loads or dumps.
The timer contains the selected operation, retaining its last output, and a
length checksum. Exact validation and fixture construction are outside it.
ROUNDS=0 retains input/validation costs for whole-process startup observations.
"""
import json
import sys
from time import perf_counter
from typing import Any


def fixture(rows: int) -> str:
    parts: list[str] = []
    for index in range(rows):
        parts.append('{"id":' + str(index) + ',"name":"row-' + str(index)
                     + '","count":' + str(index * 3)
                     + ',"ok":true,"values":[' + str(index) + ',null,-7]}')
    return "[" + ",".join(parts) + "]"


def fingerprint(text: str) -> int:
    # Advisory witness checksum; correctness is exact string equality below.
    value = 0
    for char in text:
        value = (value * 131 + ord(char)) % 2147483647
    return value


mode = sys.argv[1] if len(sys.argv) > 1 else "loads"
rows = int(sys.argv[2]) if len(sys.argv) > 2 else 32
rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 300
batches = int(sys.argv[4]) if len(sys.argv) > 4 else 1
warmups = int(sys.argv[5]) if len(sys.argv) > 5 else 0
if mode not in ("loads", "dumps") or rows < 1 or rounds < 0 or batches < 1 or warmups < 0:
    raise ValueError("expected loads/dumps, positive rows/batches, nonnegative rounds/warmups")
source = fixture(rows)
decoded: Any = json.loads(source)
encoded = json.dumps(decoded, separators=(",", ":"))
if encoded != source or len(decoded) != rows:
    raise ValueError("initial complete JSON result differs from the source fixture")
print("witness before", mode, rows, len(source), fingerprint(encoded), "exact")
print("rounds", rounds)

for batch in range(warmups + batches):
    checksum = 0
    start = perf_counter()
    if mode == "loads":
        for _ in range(rounds):
            decoded = json.loads(source)
            checksum += len(decoded)
    else:
        for _ in range(rounds):
            encoded = json.dumps(decoded, separators=(",", ":"))
            checksum += len(encoded)
    elapsed = perf_counter() - start
    if checksum != rounds * (rows if mode == "loads" else len(source)):
        raise ValueError("iteration checksum changed")
    if mode == "loads":
        encoded = json.dumps(decoded, separators=(",", ":"))
    if encoded != source:
        raise ValueError("complete JSON result changed after the timed batch")
    print("witness after", batch, mode, rows, len(encoded), fingerprint(encoded), "exact", checksum)
    print("warmup_seconds" if batch < warmups else "seconds", elapsed)
