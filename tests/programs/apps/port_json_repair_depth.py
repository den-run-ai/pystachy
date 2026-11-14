# pystachy: dynamic-any
# Three regressions of the json_repair port in one program, as each program that imports the port
# compiles all of it: the recursion limit in repair, valid input nested past the native codec's
# former budget, and comments before values.
from typing import Any
from json_repair import loads, repair_json
from json_repair.json_parser import JSONParser


def rejected(text: str) -> None:
    try:
        loads(text, skip_json_loads=True)
    except ValueError as exc:
        assert str(exc) == "Input nesting exceeds the supported parser recursion depth."
    else:
        raise AssertionError("unbounded repair accepted")


# Deep repair raises RecursionError at the recursion limit, which the facade
# reports as upstream's ValueError, in CPython and natively. Exercise ordinary
# nesting and the reparsing cycles that contain no new braces.
def repair_depth() -> None:
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

    # Comments separated by ignored prose or numbers recurse once for each alternation, as upstream
    # does: a few repair, and many exceed the recursion limit with upstream's ValueError.
    for prefix in ["/* c */ ignored ", "/* c */ 1 ", "// c\n ignored "]:
        assert loads(prefix * 40 + "{}", skip_json_loads=True) == {}
        try:
            loads(prefix * 2000 + "{}", skip_json_loads=True)
        except ValueError as exc:
            assert str(exc) == "Input nesting exceeds the supported parser recursion depth."
        else:
            raise AssertionError("alternating comments and prose did not reach the recursion limit")
    print("alternating comments and prose follow the recursion limit")

    # Retain comment log order and the found-value flag, including empty containers.
    parser = JSONParser("/* first */ ignored // second\n 123 # third\n {}", None, True)
    assert parser.parse_json(record_top_level_value=True) == {}
    assert parser._last_parse_found_value
    assert [entry["text"] for entry in parser.logger] == [
        "Found block comment: /* first */, ignoring",
        "Found line comment: // second, ignoring",
        "Found line comment: # third, ignoring",
    ]
    for suffix in ["ignored", "123", '"key": 1}']:
        parser = JSONParser("/* comment */ " + suffix, None, False)
        assert parser.parse_json(record_top_level_value=True) == ""
        assert not parser._last_parse_found_value
    parser = JSONParser("/* comment */ []", None, False)
    assert parser.parse_json(record_top_level_value=True) == []
    assert parser._last_parse_found_value
    print("comment logs and top-level flags preserved")

    # A parser stays usable after the recursion limit or a strict error unwinds it.
    parser = JSONParser("[" * depth + "0", None, False)
    try:
        parser.parse()
    except RecursionError:
        pass
    else:
        raise AssertionError("deep parser accepted")
    parser.json_str = "[7]"
    parser.index = 0
    assert parser.parse() == [7]

    parser = JSONParser('{"":1}', None, False, strict=True)
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


# Valid JSON nested beyond the native codec's former fixed budget of 256 containers takes the
# facade's json.loads() fast path and returns the value, as upstream does on CPython (#1021).
def valid_depth() -> None:
    for depth in [256, 257, 300, 400]:
        text = "[" * depth + "]" * depth
        out: Any = repair_json(text)
        print(depth, out == text)
        value: Any = loads('{"a":' * depth + "1" + "}" * depth)
        levels = 0
        while isinstance(value, dict):
            value = value["a"]
            levels += 1
        print(levels, value)

    # The fast path's codec nests as CPython's does, whatever the recursion limit: 9,998 containers
    # decode and encode again, and one more raises the decoder's RecursionError out of the fast
    # path in both implementations.
    text = "[" * 9998 + "]" * 9998
    out = repair_json(text)
    print(len(out), out == text)
    try:
        repair_json("[" + text + "]")
        print("accepted")
    except RecursionError as exc:
        print(exc)


# Original regressions for comments before object values and array elements.
# The intended values are specified independently of the repair parser.
def comments() -> None:
    cases = [
        ('{"a": /* comment */ 1}', '{"a": 1}'),
        ('{"a": // note\n "x", "b": 2}', '{"a": "x", "b": 2}'),
        ('{"a": /* c */ {"b": 1}}', '{"a": {"b": 1}}'),
        ('{"a": # c\n true}', '{"a": true}'),
        ('{"a": /* c */ [1, 2], "b": 3}', '{"a": [1, 2], "b": 3}'),
        ('{"a": /* first */ // second\r\n # third\n null}', '{"a": null}'),
        ('{"a": /* c */ "", "b": 2}', '{"a": "", "b": 2}'),
        ('{"a": /* c */ false}', '{"a": false}'),
        ('{"a": /* c */ -1.25}', '{"a": -1.25}'),
        ('{"a": /* c */ 12345678901234567890}', '{"a": 12345678901234567890}'),
        ('[{"a": /* c */ {"b": /* d */ [1, false]}}, 2]',
         '[{"a": {"b": [1, false]}}, 2]'),
        ('[/* c */12]', '[12]'),
        ('[/* c */[1, 2]]', '[[1, 2]]'),
        ('[/* a *//* b */12]', '[12]'),
        ('[/* c */]', '[]'),
        ('[1, /* c */]', '[1]'),
        ('[/* c */"", /* d */true, /* e */null]', '["", true, null]'),
        ('[// c\n12, # d\n13]', '[12, 13]'),
    ]
    for text, expected in cases:
        for strict in [False, True]:
            for skip in [False, True]:
                assert repair_json(text, strict=strict, skip_json_loads=skip) == expected
        print(repair_json(text))

    # A stray slash at the start of an item or value drops what follows it, as upstream does.
    for text in ['[/1,2]', '[/abc]', '{"k":/42}', '{"k":/ /*x*/true}']:
        print(text, repair_json(text))

    # A comment without a value must not consume the next member or invent one.
    for text in ['{"a": /* c */, "b": 2}', '{"a": /* c */}',
                 '{"a": /* c */', '{"a": /* unclosed']:
        print(repair_json(text))
        try:
            repair_json(text, strict=True)
        except ValueError:
            print('missing value')
        else:
            raise AssertionError('strict mode accepted a missing value')

    for comment in ['/* note */', '// note\n', '# note\n']:
        raw = f'{{{comment} "a" {comment}: 1 {comment}, {comment} "b": 2 {comment}}}'
        for strict in [False, True]:
            parsed = loads(raw, strict=strict, logging=True)
            assert parsed[0] == {'a': 1, 'b': 2}
            assert len(parsed[1]) == 5
        assert loads('{' + comment + '}', strict=True) == {}

    try:
        loads('{/* unclosed }', strict=True)
    except ValueError as exc:
        assert str(exc) == 'Parsed object is empty but contains extra characters in strict mode.'
    else:
        raise AssertionError('strict mode accepted an unclosed comment')

    # Large runs of comments use a loop, and comment logging remains present.
    assert repair_json('{"a":' + '/* c */' * 1200 + '1}') == '{"a": 1}'
    result = loads('{"a": /* one */ // two\n # three\n 1}', logging=True)
    assert result[0] == {'a': 1}
    assert len(result[1]) == 3
    print('comments preserved values')


repair_depth()
valid_depth()
comments()
