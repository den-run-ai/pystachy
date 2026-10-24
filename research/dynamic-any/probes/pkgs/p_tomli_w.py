# pystachy: dynamic-any
import tomli_w
print(tomli_w.dumps({"title": "x", "n": 1, "pi": 3.14, "ok": True, "tags": ["a", "b"],
                     "owner": {"name": "Tom", "age": 3}, "points": [{"x": 1}, {"x": 2.5}]}))
