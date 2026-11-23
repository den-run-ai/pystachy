# pystachy: dynamic-any
# a value of object that holds an Any value is the object that the Any value holds: `is` and
# `is not` with that object, of a class, a list or a str, from either side, also as a list's
# item, a field and a function's result, where the Any value's box is not the object
# (object_storage_dynamic_identity_typed.py: a list or a dict of typed items)
from typing import Any


class P:
    def __init__(self, v: int) -> None:
        self.v = v


class Holder:
    def __init__(self, item: object) -> None:
        self.item = item


def held(x: Any) -> object:
    return x


def same(x: object, y: P) -> bool:
    return x is y


def main() -> None:
    p = P(1)
    q = P(2)
    a: Any = p
    o: object = a
    typed: object = p
    print(o is p, p is o, o is not p, p is not o, o is q, q is o)
    print(o is typed, typed is o, o is not typed, typed is not o)
    print(same(o, p), same(o, q), same(held(a), p), same(Holder(a).item, p))
    items: list[object] = [a, typed]
    print(items[0] is p, items[0] is items[1], items[1] is items[0], p is items[0])
    xs = [1, 2]
    b: Any = xs
    ob: object = b
    print(ob is xs, xs is ob, ob is not xs, ob is [1, 2])
    s = "".join(["a", "b"])
    c: Any = s
    oc: object = c
    print(oc is s, s is oc, oc == s)
    n: Any = None
    on: object = n
    print(on is None, on is p, p is on)


main()
