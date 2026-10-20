# pystachy: dynamic-any
import json

data = {"name": "x", "n": 3, "items": [1, "two", None]}
print(json.dumps(data, sort_keys=True))
