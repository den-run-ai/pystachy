# pystachy: dynamic-any
import json

print(json.dumps({"name": "x", "n": 3, "items": [1, "two", None, True]}, sort_keys=True))
