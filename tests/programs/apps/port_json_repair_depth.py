# pystachy: dynamic-any
# Deep repair raises RecursionError at the recursion limit, which the facade
# reports as upstream's ValueError, in CPython and natively. Exercise ordinary
# nesting and the reparsing cycles that contain no new braces.
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

# Nesting below the recursion limit still repairs, as upstream does on CPython;
# a fixed budget of 256 active array/object/string parses rejected both.
nested: Any = loads("[" * 300 + "0" + "]" * 300, skip_json_loads=True)
levels = 0
while isinstance(nested, list):
    nested = nested[0]
    levels += 1
assert levels == 300 and nested == 0
nested = loads('[{"a":' * 130 + "0" + "}]" * 130, skip_json_loads=True)
levels = 0
while isinstance(nested, list):
    nested = nested[0]["a"]
    levels += 1
assert levels == 130 and nested == 0
print("nesting below the recursion limit repaired")

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
assert parser._last_parse_found_value
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

# A parser stays usable after the recursion limit or a strict error unwinds it.
parser = JSONParser("[" * depth + "0", False)
try:
    parser.parse()
except RecursionError:
    pass
else:
    raise AssertionError("deep parser accepted")
parser.json_str = "[7]"
parser.index = 0
assert parser.parse() == [7]

parser = JSONParser('{"":1}', False, strict=True)
try:
    parser.parse()
except ValueError:
    pass
else:
    raise AssertionError("strict empty key accepted")
parser.json_str = '{"ok":1}'
parser.index = 0
assert parser.parse() == {"ok": 1}
print("parser reusable after exceptions")
