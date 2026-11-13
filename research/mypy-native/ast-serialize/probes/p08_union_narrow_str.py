# Narrowing a value of a dict of bool, str and two list types to str (in a function)
Value = bool | str | list[tuple[int, list[str]]] | list[tuple[int, str]]


def make() -> dict[str, Value]:
    d: dict[str, Value] = {}
    d["h"] = "abc"
    return d


def use(d: dict[str, Value]) -> int:
    v = d["h"]
    if isinstance(v, str):
        return len(v)
    return -1


def use2(d: dict[str, Value]) -> str:
    v = d["h"]
    if isinstance(v, str):
        return v.upper()
    return ""


print(use(make()), use2(make()))
