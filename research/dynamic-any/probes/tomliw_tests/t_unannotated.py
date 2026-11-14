# pystachy: dynamic-any
# typed-looking but unannotated documents built in locals, passed to an Any API
import tomli_w

empty = {"x": 1}
print(repr(tomli_w.dumps(empty)))
doc = {"a": "x", "b": "y"}
print(tomli_w.dumps(doc))
nested = {"t": {"k": "v"}, "arr": [["a"], ["b"]]}
print(tomli_w.dumps(nested))
rows = {}
for i in range(3):
    rows["r" + str(i)] = {"n": i, "name": "row" + str(i)}
print(tomli_w.dumps({"rows": rows}))
