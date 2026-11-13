# Narrowing the values of a dict of bool, str and two list types
Value = bool | str | list[tuple[int, list[str]]] | list[tuple[int, str]]


def make() -> dict[str, Value]:
    d: dict[str, Value] = {}
    d["h"] = "abc"
    d["b"] = True
    d["l"] = [(1, "x")]
    return d


d = make()
v = d["h"]
assert isinstance(v, str)
print(v.upper())
w = d["b"]
if isinstance(w, bool):
    print(not w)
x = d["l"]
if isinstance(x, list):
    print(len(x))
