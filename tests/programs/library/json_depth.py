# JSON nesting counts against sys.setrecursionlimit() like other native recursion, and stops at
# 2,000 containers. Below both bounds, typed decoding, raw_decode() and encoding match CPython;
# past 2,000 containers (under a raised limit) they raise CPython's RecursionError messages,
# which CPython's own codec raises past its larger bound.
import json
import sys


def nest(depth: int) -> "json.JSONValue":
    value: json.JSONValue = []
    for _ in range(depth - 1):
        outer: list[json.JSONValue] = [value]
        value = outer
    return value


def roundtrip(source: str) -> None:
    print(len(source), json.dumps(json.loads(source), separators=(",", ":")) == source)


def rejected(source: str) -> None:
    try:
        json.loads(source)
        print("accepted")
    except RecursionError as exc:
        print(exc)


def main() -> None:
    decoder = json.JSONDecoder()
    for depth in [256, 257, 300, 400]:
        roundtrip("[" * depth + "0" + "]" * depth)
        roundtrip('{"a":' * depth + "0" + "}" * depth)
        roundtrip('[{"a":' * (depth // 2) + '"x"' + "}]" * (depth // 2))
        value, end = decoder.raw_decode("é " + "[" * depth + "]" * depth + " tail", 2)
        print(end, len(json.dumps(value)), len(json.dumps(nest(depth))))
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(5000)
    try:
        roundtrip("[" * 2000 + "]" * 2000)
        print(len(json.dumps(nest(2000))))
        rejected("[" * 10000 + "]" * 10000)
        rejected('{"a":' * 10000 + "0" + "}" * 10000)
        rejected('[{"a":' * 5000 + "0" + "}]" * 5000)
        try:
            json.dumps(nest(10000))
            print("encoded")
        except RecursionError as exc:
            print(exc)
    finally:
        sys.setrecursionlimit(limit)
    print(sys.getrecursionlimit())


main()
