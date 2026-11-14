# pystachy: dynamic-any
from toolz.dicttoolz import get_in, assoc_in, merge, valmap
doc = {"a": [{"b": 1}, {"b": "two"}], "c": 3}
print(get_in(["a", 1, "b"], doc), get_in(["a", 5], doc, "none"))
print(assoc_in(doc, ["x", "y"], 2.5))
print(merge({"a": 1}, {"b": "x"}), valmap(str, {"a": 1, "b": 2.5}))
