# a list, dict or set display stored as object that is empty, or whose items no one type holds:
# its items are values of object, and a view reads it as CPython's container
def show(v: object) -> str:
    x: object = v
    if isinstance(x, list):
        return f"list {len(x)} {x}"
    if isinstance(x, dict):
        return f"dict {len(x)} {x} {x.get('k')}"
    if isinstance(x, (set, frozenset)):
        return f"set {len(x)} {x}"
    if isinstance(x, tuple):
        return f"tuple {len(x)} {x}"
    return f"other {x}"


def main() -> None:
    e: object = []
    d: object = {}
    s: object = set()
    f: object = frozenset()
    t: object = ()
    m: object = [1, "two", [3], None, (4, "x")]
    md: object = {"a": 1, "b": "two", "c": [3]}
    nested: list[object] = [[], {}, [1, [2, "x"]]]
    print(show(e), show(d), show(s), show(f), show(t))
    print(show(m), show(md))
    for n in nested:
        print(show(n))
    if isinstance(m, list):
        inner = m[2]
        if isinstance(inner, list):
            print(inner[0], m.index(None), m.count("two"))


main()
