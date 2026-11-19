# pystachy: dynamic-any
# A := in one item of a list or dict display binds a name that a later item reads, in a module
# that compiles typing.Any as dynamic values. Dry runs of the items decide whether the display
# holds Any values before any item runs, and once rejected the later read as one before the
# name's first assignment, where CPython runs the items in order (test_named_expressions)
from typing import Any


def spam(a):
    return a


def main() -> None:
    def local(a):
        return a

    x: Any = 3
    b = [z := x, z, z + 1]
    print(b, z)
    res = [[y := spam(i), i / y] for i in range(1, 5)]
    print(res, y)
    res2 = [[v := local(i), i / v] for i in range(1, 3)]
    print(res2, v)
    d = {"first": (w := x * 2), "again": w}
    print(d, w)
    k = {(key := "k"): key + "!"}
    print(k, key)
    nested = [[n := x], n]
    print(nested, n)
    mixed = [m := 1, "s" + str(m)]
    print(mixed, m)
    # (an untyped empty item: the items before it type it, and [e] reads e)
    empty = [(e := x), [e], []]
    print(empty, e)
    lists = [g := [1], g, []]
    print(lists, g)


main()
