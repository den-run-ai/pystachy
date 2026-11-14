# pystachy: dynamic-any
import copy
doc = {"a": [1, "two", {"b": None}], "t": (1, 2.5)}
d2 = copy.deepcopy(doc)
d2["a"][2]["b"] = 3
print(doc, d2, copy.copy(doc) == doc)
