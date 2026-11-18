# A tuple's in, count() and index() find a union's object, None or list by its identity first, as
# CPython's do: objects of classes without __eq__, and a list holding a NaN.
class C:
    def __init__(self, n: int) -> None:
        self.n = n


class D:
    pass


def objects(x: C | D, y: C | D) -> None:
    print(x in (x,), x in (y,), (x, y).count(x), (y, x).index(x))


def maybe(x: C | D | None, y: C | D | None) -> None:
    print(x in (y,), (x, y).count(y), None in (x,))


def plain(x: C | D, c: C) -> None:
    print(c in (x,), x in (c,), (x, c).count(c))


def lists(x: int | list[float], y: int | list[float]) -> None:
    print(x in (x,), x in (y,), (y, x).count(x))


c = C(1)
objects(c, D())
objects(D(), D())
objects(c, c)
maybe(None, None)
maybe(c, None)
maybe(c, c)
plain(c, c)
plain(D(), c)
nan = float("nan")
xs = [nan]
lists(xs, xs)
lists(xs, [1.0])
lists(2, 2)
