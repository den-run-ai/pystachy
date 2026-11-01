# pystachy: dynamic-any
# The port bounds active repair parses independently of native stack exhaustion.
# Exercise ordinary nesting and the reparsing cycles that contain no new braces.
from typing import Any
from json_repair import loads
from json_repair.json_parser import JSONParser


def rejected(text: str) -> None:
    try:
        loads(text, skip_json_loads=True)
    except ValueError as exc:
        assert str(exc) == "Input nesting exceeds the supported parser recursion depth."
    else:
        raise AssertionError("unbounded repair accepted")


depth = 512
rejected("[" * depth + "0" + "]" * depth)
rejected('{"a":' * depth + "0" + "}" * depth)
rejected("(" * depth + "0" + ")" * depth)
rejected('[{"a":' * depth + "0" + "}]" * depth)
# Each additional object re-enters parse_object directly, bypassing parse_json.
rejected('{"a":0}' + ',"a":0}' * depth)
# Fenced JSON can recursively re-enter parse_string without adding containers.
rejected('{"a":' + '"```json ' * depth + "1" + '```"' * depth + "}")
print("six recursive repair paths rejected")

# Wide or sequential input must not consume a cumulative recursion budget.
value: Any = loads("[" + "[1]," * 400 + "]", skip_json_loads=True)
assert len(value) == 400 and value[0] == [1] and value[399] == [1]
assert loads("/* comment */ " * 400 + "[1]", skip_json_loads=True) == [1]
assert loads('{a: [1, {b: "ok"}]}') == {"a": [1, {"b": "ok"}]}
print("wide and sequential repairs preserved")

# Comments separated by ignored prose or numbers formerly grew the native call
# stack without entering a guarded container/string parse. They are sequential
# input, so consume them iteratively instead of imposing the nesting budget.
for prefix in ["/* c */ ignored ", "/* c */ 1 ", "// c\n ignored "]:
    assert loads(prefix * 2000 + "{}", skip_json_loads=True) == {}
print("alternating comments and prose stay iterative")

# Retain comment log order and the found-value flag, including empty containers.
parser = JSONParser("/* first */ ignored // second\n 123 # third\n {}", True)
assert parser.parse_json(record_top_level_value=True) == {}
assert parser._last_parse_found_value and parser._parse_depth == 0
assert [entry["text"] for entry in parser.logger] == [
    "Found block comment: /* first */, ignoring",
    "Found line comment: // second, ignoring",
    "Found line comment: # third, ignoring",
]
for suffix in ["ignored", "123", '"key": 1}']:
    parser = JSONParser("/* comment */ " + suffix, False)
    assert parser.parse_json(record_top_level_value=True) == ""
    assert not parser._last_parse_found_value
parser = JSONParser("/* comment */ []", False)
assert parser.parse_json(record_top_level_value=True) == []
assert parser._last_parse_found_value
print("comment logs and top-level flags preserved")

# Seeding the private counter exercises the exact boundary without relying on
# CPython's interpreter recursion limit (which can fire before the native cap).
for kind in range(3):
    text = "]" if kind == 0 else "}" if kind == 1 else '"ok"'
    parser = JSONParser(text, False)
    parser._parse_depth = 255
    if kind == 0:
        assert parser.parse_array() == []
    elif kind == 1:
        assert parser.parse_object() == {}
    else:
        assert parser.parse_string() == "ok"
    assert parser._parse_depth == 255
    parser.index = 0
    parser._parse_depth = 256
    try:
        if kind == 0:
            parser.parse_array()
        elif kind == 1:
            parser.parse_object()
        else:
            parser.parse_string()
    except RecursionError as exc:
        assert str(exc) == "maximum repair parser depth exceeded"
    else:
        raise AssertionError("repair boundary accepted")
    assert parser._parse_depth == 256 and parser.index == 0
print("exact repair boundary preserved")

# Restore the counter after both the depth guard and ordinary parser exceptions.
parser = JSONParser("[" * depth + "0", False)
try:
    parser.parse()
except RecursionError:
    pass
else:
    raise AssertionError("deep parser accepted")
assert parser._parse_depth == 0
parser.json_str = "[7]"
parser.index = 0
assert parser.parse() == [7] and parser._parse_depth == 0

parser = JSONParser('{"":1}', False, strict=True)
try:
    parser.parse()
except ValueError:
    pass
else:
    raise AssertionError("strict empty key accepted")
assert parser._parse_depth == 0
parser.json_str = '{"ok":1}'
parser.index = 0
assert parser.parse() == {"ok": 1} and parser._parse_depth == 0
print("repair depth restored after exceptions")
