# tomli_w.dumps() of ports/tomli_w on the values a TOML document holds: strings with escapes,
# control characters, non-ASCII text and keys that need quotes, multiline strings, integers at
# the 64-bit limits, floats, booleans, arrays, nested arrays, tuples, and the indent= option.
# Each container holds values of one type: a dict or list of mixed types needs M4.
import tomli_w

print(tomli_w.__version__, tomli_w.__all__)

# strings, and keys that are bare or quoted
print(repr(tomli_w.dumps({"a": "x"})))
print(tomli_w.dumps({"title": 'TOML "example"', "path": "C:\\dir", "ctrl": "tab\there\x01\x7f"}))
print(tomli_w.dumps({"k\x00ey": "v\x1f", "\x7f": "  \ufeff", "tab\tkey": 'a\\b"c', "\u00e9": "\U0010ffff"}))
print(tomli_w.dumps({"n\u00e9v": "Zo\u00eb \u20ac \U0001f600", "a b": "space", "": "empty key", "ok-key_1": "bare"}))
print(tomli_w.dumps({"c1": "\x80\x9f\xa0\xff", "bs": "\x08\x0c\r\n\x1b"}))
# the first and last characters of each length in UTF-8, NEL and the line and paragraph separators
print(tomli_w.dumps({"߿ࠀ": "\x7f\x80߿ࠀ￿\U00010000\x85  "}))

# multiline strings (upstream's test_multiline), and the same text without the option
ml = "This is longer than threshold!\nShould be formatted as a multiline basic string"
print(tomli_w.dumps({"ml_string": ml}, multiline_strings=True))
print(tomli_w.dumps({"text": "line1\nline2\r\nline3"}, multiline_strings=True))
print(tomli_w.dumps({"m": 'a\\\nb """ c\x08\r\nd\te\x0c'}, multiline_strings=True))
print(tomli_w.dumps({"s": 'no newline but "quotes"', "cr": "a\rb"}, multiline_strings=True))
print(tomli_w.dumps({"text": "line1\nline2"}))

# integers, floats and booleans
print(tomli_w.dumps({"n": 1, "big": 9223372036854775807, "neg": -9223372036854775807 - 1, "zero": -0}))
print(tomli_w.dumps({"pi": 3.14159, "inf": float("inf"), "ninf": float("-inf"), "zero": -0.0, "e": 6.02e23}))
print(tomli_w.dumps({"a": 1e16, "b": 1e-7, "c": 0.1 + 0.2, "d": 5e-324, "e": 1.7976931348623157e308, "f": float("nan"), "g": 123456789.0, "h": 2e16}))
print(tomli_w.dumps({"on": True, "off": False}))

# arrays, nested arrays and tuples (upstream's test_tuple, of one type)
print(tomli_w.dumps({"arr": [1, 2, 3], "empty": [], "neg": [-1]}))
print(tomli_w.dumps({"matrix": [[1, 2], [3, 4], []]}))
print(tomli_w.dumps({"t": (1, 2, 3), "u": (4, 5, 6)}))
print(tomli_w.dumps({"nested": ((1, 2), (3, 4))}))
print(tomli_w.dumps({"flags": [True, False]}))
print(tomli_w.dumps({"floats": [0.5, -1e300, float("inf")]}))

# indent= (upstream's test_array_indent_override, of one type)
data = {"k0": [["v1", "v2"], ["v3", "v4"]]}
print(tomli_w.dumps(data, indent=2))
print(tomli_w.dumps(data, indent=0))
print(tomli_w.dumps({"deep": [[[1]], [[2, 3]]]}, indent=1))
print(tomli_w.dumps({"t": {"x": 1, "y": 2}}, indent=0))
try:
    tomli_w.dumps({"a": 1}, indent=-1)
except ValueError as e:
    print("ValueError:", e)
