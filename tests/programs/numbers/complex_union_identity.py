# A complex number in a union is an object: in, count() and index() of a tuple find it by its
# identity first, as CPython's do, also where a part is NaN, which no complex number equals.
def search(x: int | complex, y: int | complex) -> None:
    print(x in (x,), (x,).count(x), (y, x).index(x), x in (y,), (x, y).count(y))


def mixed(x: int | complex | None, c: complex) -> None:
    print(c in (x,), x in (c,), (x, c).count(c))


nan = float("nan")
c = complex(nan, 0.0)
search(c, 1)
search(c, c)
search(c, complex(nan, 0.0))
search(complex(1, 2), complex(1, 2))
search(3, 3)
mixed(c, c)
mixed(None, c)
mixed(5, c)
