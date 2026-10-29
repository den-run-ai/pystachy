# pystachy: dynamic-any
"""Small mixed document decoded into an observed Any value on every iteration.

This complements the pyperformance loop whose returned typed JSONValue is discarded.
Keep the document short: its cursor stays in the small-integer cache, so a scanner
change cannot hide dispatch overhead behind savings on large numeric identity boxes.
"""
from typing import Any
import json
import sys
import time

source = '{"name":"alpha","n":1000,"float":1.25,"ok":true,"empty":null,"list":[1001,1002,1003,"x",false],"obj":{"a":99999,"b":-1729},"unicode":"caf\\u00e9"}'
n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
if n < 1:
    raise ValueError("iteration count must be positive")
checksum = 0
start = time.perf_counter()
for i in range(n):
    value: Any = json.loads(source)
    checksum += value["n"]
assert checksum == n * 1000
print(checksum, value)
print(time.perf_counter() - start, file=sys.stderr)
