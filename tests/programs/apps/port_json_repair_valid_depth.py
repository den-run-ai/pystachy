# pystachy: dynamic-any
# Valid JSON nested beyond the native codec's former fixed budget of 256 containers takes the
# facade's json.loads() fast path and returns the value, as upstream does on CPython (#1021).
import sys
from typing import Any
from json_repair import loads, repair_json

for depth in [256, 257, 300, 400]:
    text = "[" * depth + "]" * depth
    out: Any = repair_json(text)
    print(depth, out == text)
    value: Any = loads('{"a":' * depth + "1" + "}" * depth)
    levels = 0
    while isinstance(value, dict):
        value = value["a"]
        levels += 1
    print(levels, value)

# Under a raised recursion limit, 2,000 levels decode; nesting beyond the codec's bound
# raises RecursionError out of the fast path in both implementations.
limit = sys.getrecursionlimit()
sys.setrecursionlimit(5000)
try:
    out = repair_json("[" * 2000 + "]" * 2000)
    print(len(out))
    try:
        repair_json("[" * 10000 + "]" * 10000)
        print("accepted")
    except RecursionError as exc:
        print(exc)
finally:
    sys.setrecursionlimit(limit)
