# Deliberate prototype boundaries: JSON integers are signed 64-bit values, and encoded containers
# count against sys.setrecursionlimit() (one counted call for each) and stop at 2,000. CPython's
# C encoder accepts all of these values: its own bound, 9,998 containers on Linux, does not
# depend on the recursion limit. (Decoding nests as CPython's decoder does:
# tests/programs/library/json_deep_nesting.py.)
import json
import sys


def nest(depth: int) -> "json.JSONValue":
    value: json.JSONValue = [0]
    for _ in range(depth - 1):
        outer: list[json.JSONValue] = [value]
        value = outer
    return value


def encode(value: "json.JSONValue") -> None:
    try:
        json.dumps(value)
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
    # At the default limit of 1,000: about 1,000 encoded containers.
    encode(nest(1200))
    # A raised limit reaches the fixed bound, which keeps the native stack from overflowing.
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(5000)
    try:
        encode(nest(2000))
        encode(nest(2001))
    finally:
        sys.setrecursionlimit(limit)


main()
