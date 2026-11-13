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

# The fast path's decoder nests as CPython's does, whatever the recursion limit: loads() returns
# 9,998 nested containers.
deep: Any = loads("[" * 9998 + "]" * 9998)
levels = 0
while isinstance(deep, list) and len(deep) > 0:
    deep = deep[0]
    levels += 1
print(levels)

# Under a raised recursion limit, 2,000 levels decode and encode; nesting beyond the decoder's
# bound raises RecursionError out of the fast path in both implementations.
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
