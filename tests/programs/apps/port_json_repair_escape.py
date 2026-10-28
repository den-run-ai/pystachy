# pystachy: dynamic-any
"""Escape replacement preserves metadata and malformed-input repair behavior."""
import json

from json_repair import repair_json
from json_repair.parse_string import StringParseState, _append_string_content, _replace_last_escape


checks = 0
for prefix in ["", "x", "{", "}", "{{}", "}{", "[", "][", "[x]", "{[é🌲"]:
    for replacement in ["", "\\", "\\\\", '"', "\n", "{", "}", "[", "]", "é", "🌲"]:
        state = StringParseState()
        _append_string_content(state, prefix + "\\")
        _replace_last_escape(state, replacement)
        expected = prefix + replacement
        braces = 0
        bracket: int | None = None
        for index, char in enumerate(expected):
            if char == "{":
                braces += 1
            elif char == "}" and braces > 0:
                braces -= 1
            elif char == "[":
                bracket = index + 1
            elif char == "]":
                bracket = None
        assert state.string_acc == expected
        assert state.object_value_unmatched_opening_braces == braces
        assert state.regex_character_class_start == bracket
        checks += 1
print("metadata comparisons", checks)

sources = [
    '{"a":"\\u007b}x',
    '{"a":"{\\u007d}x',
    '{"a":"\\u005b\'\"]tail",}',
    '{"a":"x\\nx\\tend",}',
    '{"a":"\\u007bvalue} trailing",}',
    '{"a":"{value\\u007d trailing",}',
    '{"a":"\\x7bvalue\\x7d trailing",}',
    '{"a":"\\u005b\"\\u005d tail",}',
    '{"a":"[x\\u005d tail",}',
    '{"a":"\\\\\\\\end",}',
    '{"a":"\\\\\\\"quoted\\\" tail",}',
    '{"a":"„text\\\" tail",}',
    '{"a":"left\\”right",}',
    '{"a":"left\\„right",}',
    '{"a":"\\uZZZZ tail",}',
    '{"a":"[é🌲{tail\\',
]
for length in [2, 3, 4]:
    for following in ["x", '"']:
        sources.append('{"a":"p' + "\\" * length + following + 'q",}')
for source in sources:
    for stable in [False, True]:
        for strict in [False, True]:
            try:
                result = repair_json(source, return_objects=True, skip_json_loads=True,
                                     logging=True, stream_stable=stable, strict=strict)
                print(json.dumps(result, ensure_ascii=True))
            except ValueError as error:
                print("ValueError", str(error))
