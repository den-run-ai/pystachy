# pystachy: dynamic-any
from flatten_json import flatten
print(flatten({"a": {"b": 1, "c": [2, "x", {"d": None}]}, "e": 2.5}))
