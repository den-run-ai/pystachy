# pystachy: dynamic-any
# The Any decoder and encoder nest as json's do and as CPython's: at the default recursion limit
# and under a raised one, with CPython's RecursionError messages past the bound of 9,998
# containers (tests/programs/inference/dynany_json_deep_nesting.py has the bound).
import json
import sys
from typing import Any

try:
    from json import _raw_decode as raw_decode
except ImportError:
    def raw_decode(s: str, idx: int = 0) -> tuple[Any, int]:
        return json.JSONDecoder().raw_decode(s, idx)


def arrays(depth: int) -> Any:
    value: Any = []
    for _ in range(depth - 1):
        value = [value]
    return value


def objects(depth: int) -> Any:
    value: Any = {}
    for _ in range(depth - 1):
        value = {"a": value}
    return value


def roundtrip(source: str) -> None:
    value: Any = json.loads(source)
    print(len(source), json.dumps(value, separators=(",", ":")) == source)


def rejected(source: str) -> None:
    try:
        value: Any = json.loads(source)
        print("accepted", len(value))
    except RecursionError as exc:
        print(exc)


def main() -> None:
    for depth in [256, 257, 300, 400]:
        roundtrip("[" * depth + "0" + "]" * depth)
        roundtrip('{"a":' * depth + "0" + "}" * depth)
        roundtrip('[{"a":' * (depth // 2) + '"x"' + "}]" * (depth // 2))
        found, end = raw_decode("é " + "[" * depth + "]" * depth + " tail", 2)
        value: Any = found
        print(end, len(json.dumps(value)), len(json.dumps(arrays(depth))), len(json.dumps(objects(depth))))
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(5000)
    try:
        roundtrip("[" * 2000 + "]" * 2000)
        print(len(json.dumps(arrays(2000))), len(json.dumps(objects(2000))))
        rejected("[" * 10000 + "]" * 10000)
        rejected('{"a":' * 10000 + "0" + "}" * 10000)
        rejected('[{"a":' * 5000 + "0" + "}]" * 5000)
        try:
            json.dumps(arrays(10000))
            print("encoded")
        except RecursionError as exc:
            print(exc)
    finally:
        sys.setrecursionlimit(limit)
    print(sys.getrecursionlimit())


main()
