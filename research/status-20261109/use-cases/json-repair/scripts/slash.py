import json_repair
from json_repair import repair_json
cases = ['[/1,2]', '[1, /2]', '{"k":/42}', '{"path": /usr/bin}', '{"path": /usr/bin, "n": 1}', '{"a": /regex/}',
         '{"a": 1, /"b": 2}', '["x", / "y"]', '{"k": /true}', '{"k": /"v"}']
for raw in cases:
    print(f"{raw:30} -> {repair_json(raw, return_objects=True)!r}")
