# pystachy: dynamic-any
# homogeneous and nested displays passed directly as the Any argument
import tomli_w

print(tomli_w.dumps({"a": "x", "b": "y"}))
print(tomli_w.dumps({"t": {"k": "v"}, "arr": [["a"], ["b"]], "n": [1, 2]}))
print(tomli_w.dumps({}))
