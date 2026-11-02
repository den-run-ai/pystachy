# Deliberate prototype boundaries: JSON integers are signed 64-bit values, and nested containers
# count against sys.setrecursionlimit() (two counted calls for each decoded container, one for
# each encoded one) and stop at 2,000. CPython's C codec accepts all of these inputs: its own
# bound, 9,998 containers on Linux, does not depend on the recursion limit.
import json
import sys


def nest(depth: int) -> "json.JSONValue":
    value: json.JSONValue = [0]
    for _ in range(depth - 1):
        outer: list[json.JSONValue] = [value]
        value = outer
    return value


def decode(source: str) -> None:
    try:
        json.loads(source)
        print("depth accepted")
    except RecursionError as exc:
        print(str(exc))


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
    # At the default limit of 1,000: about 500 decoded containers and 1,000 encoded ones.
    decode("[" * 600 + "0" + "]" * 600)
    encode(nest(1200))
    # A raised limit reaches the fixed bound, which keeps the native stack from overflowing.
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(5000)
    try:
        decode("[" * 2000 + "0" + "]" * 2000)
        decode("[" * 2001 + "0" + "]" * 2001)
        decode('{"a":' * 2001 + "0" + "}" * 2001)
        encode(nest(2000))
        encode(nest(2001))
    finally:
        sys.setrecursionlimit(limit)


main()
