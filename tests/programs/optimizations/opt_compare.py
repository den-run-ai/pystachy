# Containers of T | None items with containers of T items: ==, ordering, + and extend work as
# in CPython (a new list holds T | None items); None in a list or a dict, and a tuple that
# holds None


def gl(c: bool) -> list[int] | None:
    return [1] if c else None


xs: list[str | None] = ["a"]
ys = ["a"]
zs: list[str | None] = [None]
print(xs == ys, ys == xs, xs != ys, xs < ys, zs == ys, [[1]] == [gl(True)], [[1]] == [gl(False)])
print(xs + ys, ys + zs)
d: dict[str, str | None] = {"a": "b"}
e = {"a": "b"}
print(d == e, e != d, d == {"a": None}, {"a": None} == d)
t: tuple[str | None, int] = ("a", 1)
print(t == ("a", 1), ("a", 1) == t, t < ("b", 0))
zs.extend(ys)
zs += ["c"]
zs += ys
print(zs, [None] == zs[:1], [None] in [zs[:1]], zs == [None, "a", "c", "a"])
print(None in ys, ys.count(None), None in e, None not in e, None in [1, 2], None in zs, zs.count(None), zs.index(None))
u = ("a", None)
print(u, (None,), u == ("a", None), u[1] is None, len(u), sorted([("b", None), ("a", None)]))
x = [1]
print(x in [[1]], x in [[2], [3]], x not in [[1]], {"k": 1} in [{"k": 1}])
print(ys < zs)
