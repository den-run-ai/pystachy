# pystachy: dynamic-any
# The Any decoder shares json's two ways of scanning strings: keys and the strings of a text of
# at most 1 KiB keep the scalar loop, while the strings of a longer text pass a 32-byte scalar
# prefix to the bulk byte scanner. Values, keys and error positions must not depend on which.
import json
from typing import Any

try:
    from json import _raw_decode as raw_decode
except ImportError:
    def raw_decode(s: str, idx: int = 0) -> tuple[Any, int]:
        return json.JSONDecoder().raw_decode(s, idx)

SMALL = " "
BIG = " " * 700 + "\n" + " " * 400  # whitespace before the value: a text of over 1 KiB


def describe(source: str) -> str:
    try:
        value: Any = json.loads(source)
    except json.JSONDecodeError as exc:
        return f"{exc.msg} {exc.pos} {exc.lineno} {exc.colno}"
    return "accepted " + str(len(value))


def main() -> None:
    count = 0
    for pad in [SMALL, BIG]:
        for size in [0, 1, 16, 31, 32, 33, 40, 100, 1500]:
            key = "k" * size
            text = "x" * size + "é雪😀"
            source = pad + '[{"' + key + '":"' + text + r'\n' + text + '"},'
            source += '{"' + key + '":"' + text + '", "' + key + r'\"' + '": "' + chr(0xD800) + '"}]'
            value: Any = json.loads(source)
            assert value[0][key] == text + "\n" + text
            assert value[1][key] == text
            assert value[1][key + '"'] == chr(0xD800)
            value[0][key] = "changed"
            assert value[1][key] == text
            count += 1
    print("objects-and-keys", count)

    for total in [1024, 1025]:
        for size in [32, 33, 1000]:
            text = "y" * size
            source = " " * (total - size - 4) + '["' + text + '"]'
            value: Any = json.loads(source)
            assert len(source.encode()) == total and value == [text]
    print("boundaries", 6)

    for pad in [SMALL, BIG]:
        for size in [0, 16, 31, 32, 33, 100, 1500]:
            run = "é" + "x" * size
            print(size, describe(pad + '["' + run + chr(1) + '"]'))
            print(size, describe(pad + '["' + run))
            print(size, describe(pad + '{"a": "' + run + r'\q"}'))
            print(size, describe(pad + '{"a": "' + run + r'\n' + run + chr(10) + '"}'))
            print(size, describe(pad + '{"' + run + chr(31) + '": 1}'))
            print(size, describe(pad + '["' + run + '", "' + run + '"]'))

    for size in [0, 33, 1500]:
        text = "z" * size + "😀"
        source = "é😀 " + '["' + text + r'\n' + text + '"] trailing' + BIG
        found, end = raw_decode(source, 3)
        doc: Any = found
        assert doc == [text + "\n" + text]
        print("raw", size, end)


main()
