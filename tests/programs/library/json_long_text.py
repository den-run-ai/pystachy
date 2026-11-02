# Strings of a text longer than 1 KiB pass a 32-byte scalar prefix to the bulk byte scanner;
# keys and the strings of shorter texts keep the scalar loop. Both ways must decode the same
# values and report the same errors at the same character positions.
import json

SMALL = " "
BIG = " " * 700 + "\n" + " " * 400  # whitespace before the value: a text of over 1 KiB
SIZES = [0, 1, 15, 16, 17, 31, 32, 33, 34, 40, 64, 65, 100, 1500]


def strings(source: str) -> list[str]:
    # The decoded value: a string, or an array of strings.
    value = json.loads(source)
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    else:
        assert isinstance(value, list)
        for item in value:
            assert isinstance(item, str)
            out.append(item)
    return out


def describe(source: str) -> str:
    try:
        json.loads(source)
    except json.JSONDecodeError as exc:
        return f"{exc.msg} {exc.pos} {exc.lineno} {exc.colno}"
    return "accepted"


def values() -> None:
    count = 0
    for pad in [SMALL, BIG]:
        for size in SIZES:
            for tail in ["", "é", "雪😀", chr(0xD800)]:
                text = "x" * size + tail
                assert strings(pad + '"' + text + '"') == [text]
                source = pad + '["' + text + '", "' + text + r'\n' + text + r'\"' + '"]'
                assert strings(source) == [text, text + "\n" + text + '"']
                count += 2
    print("values", count)


def keys() -> None:
    count = 0
    for pad in [SMALL, BIG]:
        for size in [0, 1, 31, 32, 33, 100, 1500]:
            key = "k" * size
            source = pad + '[{"' + key + '": "' + key + '"}, {"' + key + '": 1, "' + key + r'\t": 2}]'
            value = json.loads(source)
            assert isinstance(value, list)
            first = value[0]
            second = value[1]
            assert isinstance(first, dict) and isinstance(second, dict)
            assert list(first) == [key] and list(second) == [key, key + "\t"]
            assert first[key] == key and second[key] == 1 and second[key + "\t"] == 2
            count += 1
    print("keys", count)


def boundaries() -> None:
    # Texts of exactly 1024 and 1025 bytes, with strings across the 32-byte prefix.
    for total in [1024, 1025]:
        for size in [31, 32, 33, 1000]:
            text = "y" * size
            source = " " * (total - size - 2) + '"' + text + '"'
            assert len(source.encode()) == total
            assert strings(source) == [text]
            assert strings(" " * (total - size - 4) + '["' + text + '"]') == [text]
    text = "é" * 600  # 1,200 bytes, 600 characters
    assert strings('"' + text + '"') == [text]
    print("boundaries", 17)


def errors() -> None:
    for pad in [SMALL, BIG]:
        for size in [0, 15, 16, 31, 32, 33, 40, 100, 1500]:
            run = "é" + "x" * size
            print(size, describe(pad + '"' + run + chr(1) + '"'))
            print(size, describe(pad + '"' + run))
            print(size, describe(pad + '"' + run + "\\"))
            print(size, describe(pad + '"' + run + r'\q"'))
            print(size, describe(pad + '"' + run + r'\u12G4"'))
            print(size, describe(pad + '"' + run + r'\n' + run + chr(0) + '"'))
            print(size, describe(pad + '{"' + run + chr(31) + '": 1}'))
            print(size, describe(pad + '["' + run + '" "' + run + '"]'))


def raw() -> None:
    # raw_decode() starts exactly at idx, a character offset; the text after the value is long.
    decoder = json.JSONDecoder()
    for size in [0, 32, 33, 1500]:
        text = "z" * size + "😀"
        source = "é😀 " + '"' + text + r'\n' + text + '" trailing' + BIG
        value, end = decoder.raw_decode(source, idx=3)
        assert value == text + "\n" + text
        print("raw", size, end, len(source) - end)


values()
keys()
boundaries()
errors()
raw()
