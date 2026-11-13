# Deliberate prototype boundaries: JSON integers are signed 64-bit values, and json.dump() stops
# at 2,000 nested containers under a raised recursion limit. CPython accepts all of these values:
# its dump() encodes with Python code, which the recursion limit alone bounds. (json.loads() and
# json.dumps() nest as CPython's C decoder and encoder do, whatever the limit:
# tests/programs/library/json_deep_nesting.py.)
import json
import os
import sys


def nest(depth: int) -> "json.JSONValue":
    value: json.JSONValue = [0]
    for _ in range(depth - 1):
        outer: list[json.JSONValue] = [value]
        value = outer
    return value


def write(value: "json.JSONValue") -> None:
    try:
        with open(os.devnull, "w") as sink:
            json.dump(value, sink)
        print("encode depth accepted")
    except RecursionError as exc:
        print(str(exc))


def main() -> None:
    for source in ["9223372036854775808", "-9223372036854775809"]:
        try:
            json.loads(source)
            print("integer accepted")
        except OverflowError as exc:
            print(str(exc))
    # A raised limit reaches dump()'s fixed bound, which keeps the native stack from overflowing.
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(5000)
    try:
        write(nest(2000))
        write(nest(2001))
    finally:
        sys.setrecursionlimit(limit)


main()
