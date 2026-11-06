# pystachy: dynamic-any
# #485 08b: json.dumps of a nested dict/list of mixed scalar types
import json

data = {"name": "x", "n": 3, "ratio": 0.5, "ok": True, "none": None,
        "items": [1, "two", 3.0, [4, 5], {"k": "v"}]}
print(json.dumps(data, sort_keys=True))
