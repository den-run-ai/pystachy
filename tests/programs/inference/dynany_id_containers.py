# pystachy: dynamic-any
# id() of a typed list, dict, set, str or object is the identity that an Any value holding it
# has: aliases share it, equal copies do not, and it keys a cache as json_repair's schema
# validators are cached by id(schema).
from typing import Any


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return id(a) == id(b)


def cached(cache: dict[int, tuple[dict[str, Any], str]], schema: dict[str, Any]) -> str:
    hit = cache.get(id(schema))
    if hit is not None and hit[0] is schema:
        return hit[1]
    made = "validator %d" % len(cache)
    cache[id(schema)] = (schema, made)
    return made


def main() -> None:
    d: dict[str, Any] = {"a": 1}
    e: dict[str, Any] = {"a": 1}
    alias = d
    held: Any = d
    print(same(d, alias), same(d, e), id(d) == id(held), id(e) == id(held), d is held)
    xs: list[Any] = [1, 2]
    ys = xs
    zs: list[Any] = [1, 2]
    boxed: Any = xs
    print(id(xs) == id(ys), id(xs) == id(zs), id(xs) == id(boxed), id(zs) == id(boxed))
    cache: dict[int, tuple[dict[str, Any], str]] = {}
    print(cached(cache, d), cached(cache, e), cached(cache, alias), cached(cache, d), len(cache))
    typed: list[int] = [1, 2, 3]
    other = typed
    print(id(typed) == id(other), id(typed) == id([1, 2, 3]))
    names: set[str] = {"a"}
    more = names
    more.add("b")
    print(id(names) == id(more), id(names) == id({"a", "b"}), isinstance(id(names), int), id(names) != 0)
    b = Box(1)
    c = b
    any_box: Any = b
    print(id(b) == id(c), id(b) == id(Box(1)), id(b) == id(any_box))
    s = "text" + str(len(typed))
    t = s
    any_text: Any = s
    print(id(s) == id(t), id(s) == id(any_text))
    grown: list[Any] = []
    before = id(grown)
    for i in range(200):
        grown.append(i)
    print(id(grown) == before, len(grown))


main()
