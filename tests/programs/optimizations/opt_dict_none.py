# dict methods with None: d.pop(k, None) and d.get(k, default) with a default that may be None
# return V | None; a key that may be None is in no dict


def get(c: bool) -> str | None:
    return "a" if c else None


def lookup(d: dict[str, str], dflt: str | None) -> None:
    print(d.get("z", dflt), d.get("a", dflt))


d = {"a": "x", "b": "y"}
print(d.pop("q", None), d.pop("b", None), d)
lookup(d, None)
lookup(d, "q")
print(d.get(get(False)), d.get(get(True)), d.get(get(False), "dflt"), d.get(get(True), "dflt"))
e = {"a": 1}
print(get(False) in e, e.get(get(False), 5), e.get(get(True), 5), e.pop(get(False), 7), e[get(True)])
print(e.pop(get(True)), e)
f = {"a": [1]}
print(f.pop("z", None), f.get("a", None))
