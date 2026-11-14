# pystachy: dynamic-any
import json
print(json.dumps({"name": "x", "n": 3, "items": [1, "two", 3.5, None, True]}, sort_keys=True))
print(json.loads('{"a": [1, "two", {"b": null}]}')["a"][1])
