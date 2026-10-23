# pystachy: dynamic-any
"""Short case mappings preserve values and aliases on typed and dynamic paths."""
from typing import Any


def dynamic_case(s: Any) -> tuple[Any, Any, Any]:
    return s.lower(), s.upper(), s.swapcase()


for c in range(128):
    text = chr(c)
    alias = [text]
    lower = c + 32 if 65 <= c <= 90 else c
    upper = c - 32 if 97 <= c <= 122 else c
    swap = lower if lower != c else upper
    expected = (chr(lower), chr(upper), chr(swap))
    assert (text.lower(), text.upper(), text.swapcase()) == expected
    assert text.casefold() == chr(lower)
    dl, du, ds = dynamic_case(text)
    assert dl == expected[0] and du == expected[1] and ds == expected[2]
    assert alias[0] == text and ord(text) == c
print("ASCII characters", 128)

for c in range(256):
    raw = bytes([c])
    lower = c + 32 if 65 <= c <= 90 else c
    upper = c - 32 if 97 <= c <= 122 else c
    swap = lower if lower != c else upper
    expected_bytes = (bytes([lower]), bytes([upper]), bytes([swap]))
    assert (raw.lower(), raw.upper(), raw.swapcase()) == expected_bytes
    assert raw[0] == c
print("bytes", 256)

for text in ["", "\x00", "t", "F", "None", "aZ!", "中🌲", "\ud800"]:
    alias = [text]
    dl, du, ds = dynamic_case(text)
    assert dl == text.lower() and du == text.upper() and ds == text.swapcase()
    assert alias[0] == text
    print(repr(text), repr(text.lower()), repr(text.upper()), repr(text.swapcase()), repr(text.casefold()))
