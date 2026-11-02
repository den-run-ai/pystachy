# pystachy: dynamic-any
"""Ordinary runs retain exact values across escapes and chunk boundaries."""
import json
from typing import Any

from json_repair import repair_json


checks = 0
for width in [0, 1, 63, 64, 65, 127, 128, 129, 257]:
    for unit in ["a", "é🌲", "\ud800z"]:
        prefix = (unit * (width + 1))[:width]
        expected: Any = {"key": prefix + "\n" + prefix + "\tend"}
        source = '{"key":"' + prefix + "\\n" + prefix + '\\tend",}'
        # Force repair even when a future valid-input fast path accepts the source.
        result = repair_json(source, return_objects=True, skip_json_loads=True)
        assert result == expected
        # Serialization must preserve lone surrogate code points as well as values.
        assert repair_json(source, skip_json_loads=True) == json.dumps(expected)
        checks += 2

    prefix = "x" * width
    key = prefix + "\nkey"
    source = '{"' + prefix + '\\nkey":"' + prefix + '\\tend",}'
    assert repair_json(source, return_objects=True, skip_json_loads=True) == {key: prefix + "\tend"}
    checks += 1

    source = '{"key":"' + prefix + "\\"
    assert repair_json(source, return_objects=True, skip_json_loads=True) == {"key": prefix + "\\"}
    assert repair_json(source, return_objects=True, skip_json_loads=True, stream_stable=True) == {"key": prefix}
    checks += 2

print("exact span boundary checks", checks)

# A retained result must survive subsequent repairs and allocation traffic.
first = repair_json('{"key":"' + "é" * 65 + '\\nend",}', return_objects=True, skip_json_loads=True)
for _ in range(4):
    value = repair_json('{"key":"' + "ordinary text " * 16 + '\\tend",}',
                        return_objects=True, skip_json_loads=True)
    assert value == {"key": "ordinary text " * 16 + "\tend"}
assert first == {"key": "é" * 65 + "\nend"}
print("span result snapshot retained")
