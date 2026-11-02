# pystachy: dynamic-any
# The Any decoder shares the scanner with typed JSON, including object-key scans.
import json
from typing import Any


def main() -> None:
    count = 0
    for alignment in range(8):
        for size in [0, 7, 8, 9, 15, 16, 31, 32, 33]:
            key = "k" * size
            text = "x" * size + "é雪😀"
            source = " " * alignment + '[{"' + key + '":"' + text + r'\n' + text + '"},'
            source += '{"' + key + '":"' + text + '"}]'
            value: Any = json.loads(source)
            assert value[0][key] == text + "\n" + text
            assert value[1][key] == text
            value[0][key] = "changed"
            assert value[1][key] == text
            count += 1
    print("objects-and-keys", count)

    for size in [0, 7, 8, 15, 16, 31, 32, 65]:
        text = "x" * size
        source = '["' + text + r'\"' + text + r'\\' + text + r'\u0000' + text + '"]'
        value: Any = json.loads(source)
        assert value[0] == text + '"' + text + "\\" + text + chr(0) + text
        source = '{"' + text + r'\"' + text + '":"' + chr(0xD800) + '"}'
        value = json.loads(source)
        assert value[text + '"' + text] == chr(0xD800)
    print("escaped-keys-and-values", 16)

    count = 0
    for size in [0, 7, 8, 15, 16, 31, 32]:
        prefix = '{"é":"' + "x" * size + r'\n' + "y" * size
        for control in [0, 10, 31]:
            source = prefix + chr(control) + '"}'
            try:
                json.loads(source)
                assert False
            except json.JSONDecodeError as exc:
                assert exc.msg == "Invalid control character at"
                assert exc.pos == len(prefix)
                assert exc.lineno == 1
                assert exc.colno == len(prefix) + 1
            count += 1
    print("dynamic-errors", count)


main()
