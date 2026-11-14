# pystachy: dynamic-any
# #485 08e exactly as written: an unannotated encoder over a mixed document
def enc(o) -> str:
    if o is None:
        return "null"
    if isinstance(o, bool):
        return "true" if o else "false"
    if isinstance(o, (int, float)):
        return repr(o)
    if isinstance(o, str):
        return '"' + o + '"'
    if isinstance(o, list):
        return "[" + ", ".join(enc(x) for x in o) + "]"
    if isinstance(o, dict):
        return "{" + ", ".join(enc(k) + ": " + enc(v) for k, v in o.items()) + "}"
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

print(enc({"name": "x", "n": 3, "items": [1, "two", [4, 5]]}))
