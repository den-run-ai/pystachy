# pystachy: dynamic-any
# Promoting number parsing works both after the valid-JSON fast path and in repairs.
import json
from typing import Any
from json_repair import loads, repair_json


for skip in [False, True]:
    for text in ['{"key": 12345678901234567890}',
                 '{key: -12345678901234567890,}',
                 '[1180591620717411303424, -1180591620717411303424, 7]',
                 '{"outer": {"key": 12345678901234567890}}']:
        value: Any = loads(text, skip_json_loads=skip)
        print(json.dumps(value))
        print(repair_json(text, skip_json_loads=skip))
    document: Any = loads('{"key": 12345678901234567890}', skip_json_loads=skip)
    print(type(document["key"]).__name__, document["key"] + 1)

print(repair_json('{"key": 12345678901234567890}', strict=True))
