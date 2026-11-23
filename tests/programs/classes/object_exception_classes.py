# Exception classes (builtin ones, the program's, and the class of a caught exception) as values of
# object, beside a class object, other values and an exception object: printed, compared and hashed
# as class objects are, by identity, found in a list and a tuple, and tested with isinstance()
class Oops(Exception):
    pass


class Point:
    pass


class Always:
    def __eq__(self, other: object) -> bool:
        return True


def show(x: object) -> None:
    print(x, repr(x), str(x), f"{x}", type(x).__name__, callable(x), isinstance(x, type), isinstance(x, BaseException), bool(x))


def caught() -> object:
    try:
        raise KeyError("k")
    except LookupError as e:
        return type(e)


def main() -> None:
    values: list[object] = [ValueError, Oops, caught(), Point, 1, "s", None, Oops("o")]
    for v in values:
        show(v)
    a: object = ValueError
    b: object = Oops
    c: object = ValueError
    k = caught()
    print(a == b, a == c, a is c, a != b, a == ValueError, b == Oops, a is ValueError, k is KeyError, k == KeyError)
    print(hash(a) == hash(ValueError), hash(b) == hash(Oops), hash(k) == hash(KeyError))
    print([x == a for x in values], [x is b for x in values], [x != k for x in values])
    print(a in values, b in values, values.index(b), values.count(k), k in (ValueError, KeyError), a in (Point, Oops))
    w: object = Always()
    print(a == w, w == a, a != w, w != a, a == Point, Point == b)
    # (and typed: an exception class and an object, whose method CPython calls, else identity)
    print(ValueError == Always(), Always() != KeyError, Oops == Point(), Point() != Oops)


main()
