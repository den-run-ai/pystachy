# Bulk string scanning must preserve exact values and character-based positions.
# These independent expectations cover both plain strings and spans after escapes.
import json


def string_value(source: str, expected: str) -> None:
    value = json.loads(source)
    assert isinstance(value, str)
    assert value == expected


def main() -> None:
    count = 0
    sizes = [0, 1, 6, 7, 8, 9, 15, 16, 17, 31, 32, 33, 65]
    for alignment in range(8):
        for size in sizes:
            ordinary = "x" * size
            lead = " " * alignment
            string_value(lead + '"' + ordinary + '"', ordinary)
            string_value(lead + '"' + ordinary + r'\n' + ordinary + r'\"tail"',
                         ordinary + "\n" + ordinary + '"tail')
            count += 2
    print("plain-and-escaped", count)

    decoder = json.JSONDecoder()
    count = 0
    for text in ["", "é", "雪", "😀", chr(0xD800), chr(0xDFFF), "é雪😀"]:
        for size in [0, 7, 8, 15, 32]:
            ordinary = "x" * size + text + "y" * (33 - size)
            source = '"' + ordinary + r'\n' + ordinary + '"'
            expected = ordinary + "\n" + ordinary
            string_value(source, expected)
            prefixed = "é😀 " + source + " trailing"
            value, end = decoder.raw_decode(prefixed, idx=3)
            assert isinstance(value, str)
            assert value == expected
            assert end == 3 + len(source)
            assert prefixed[end:] == " trailing"
            count += 2
    string_value('"' + "x" * 15 + r'\ud83d\ude00' + "y" * 17 + '"',
                 "x" * 15 + "😀" + "y" * 17)
    print("unicode-and-raw", count + 1)

    count = 0
    for size in [0, 6, 7, 8, 15, 16, 31, 32]:
        prefix = ' \n"é' + "x" * size
        for control in [0, 1, 9, 10, 13, 31]:
            source = prefix + chr(control) + "tail\""
            try:
                json.loads(source)
                assert False
            except json.JSONDecodeError as exc:
                assert exc.msg == "Invalid control character at"
                assert exc.pos == len(prefix)
                assert exc.lineno == 2
                assert exc.colno == len(prefix) - 1
                assert exc.doc == source
            count += 1
        for ending in ["", "\\"]:
            source = prefix + ending
            try:
                json.loads(source)
                assert False
            except json.JSONDecodeError as exc:
                assert exc.msg == "Unterminated string starting at"
                assert exc.pos == 2
                assert exc.lineno == 2
                assert exc.colno == 1
            count += 1
        # After an escape, the next ordinary span must still stop at a control.
        source = prefix + r'\t' + "z" * size + chr(0) + '"'
        try:
            json.loads(source)
            assert False
        except json.JSONDecodeError as exc:
            assert exc.msg == "Invalid control character at"
            assert exc.pos == len(prefix) + 2 + size
        count += 1
    print("errors", count)


main()
