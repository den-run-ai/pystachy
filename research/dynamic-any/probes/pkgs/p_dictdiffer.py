# pystachy: dynamic-any
from dictdiffer import diff
a = {"a": 1, "b": {"c": [1, 2]}, "d": "x"}
b = {"a": 1.5, "b": {"c": [1, 3]}, "e": None}
print(list(diff(a, b)))
