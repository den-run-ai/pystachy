# pystachy: dynamic-any
"""Chunk boundaries retain snapshots, code points, regex tails and EOF behavior."""
import json

from json_repair import repair_json
from json_repair.parse_string import StringParseState, _append_string_content, _replace_last_escape


checks = 0
for width in [0, 1, 63, 64, 65, 127, 128, 129]:
    prefix = ("é🌲" * ((width + 1) // 2))[:width]
    for replacement in ["", "\n", "\\", "{[", "\ud800", "🌲"]:
        state = StringParseState()
        _append_string_content(state, prefix)
        snapshot = state.string_acc
        _append_string_content(state, "\\")
        escaped_snapshot = state.string_acc
        _replace_last_escape(state, replacement)
        assert snapshot == prefix
        assert escaped_snapshot == prefix + "\\"
        assert state.string_acc == prefix + replacement
        _append_string_content(state, "end")
        assert snapshot == prefix
        assert escaped_snapshot == prefix + "\\"
        assert state.string_acc == prefix + replacement + "end"
        checks += 1
print("snapshot and boundary checks", checks)

# The slow repair path is forced, including when the input itself is valid JSON.
# Two boundaries place the slash/whitespace/bracket on different chunks.
for width in [63, 65]:
    prefix = "é" * width
    sources = [
        '{"a":"' + prefix + '\\nend",}',
        '{"a":"[' + prefix + '\"x]tail",}',
        '{"a":"[' + prefix + '\u2003\"x]tail",}',
        '{"a":"' + prefix + '\\u005b\"x\\u005d tail",}',
        '{"a":"' + prefix + '\\u007bvalue\\u007d\u2003  ',
        '{"a":"' + prefix + '\\',
    ]
    for source in sources:
        for stable in [False, True]:
            for strict in [False, True]:
                try:
                    result = repair_json(source, return_objects=True, skip_json_loads=True,
                                         logging=True, stream_stable=stable, strict=strict)
                    print(json.dumps(result, ensure_ascii=True))
                except ValueError as error:
                    print("ValueError", str(error))

# Public return strings remain immutable across another repair and its GC traffic.
first = repair_json('{"a":"x\\nend",}', return_objects=True)
for _ in range(20):
    repair_json('{"a":"' + "x\\n" * 70 + 'end",}', return_objects=True)
assert first == {"a": "x\nend"}
print("public snapshot retained")
