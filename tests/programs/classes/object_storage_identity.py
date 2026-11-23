# 'is' and 'is not' of a value of object: None is only None; an object of a class, a str, a list
# or a class object is itself; a number is the same object as an equal number of its type stored
# from it or from a small int, a bool or a constant, as CPython's are (equal numbers computed
# apart: tests/deviations/object_number_identity.py)
class Mark:
    pass


MARK = Mark()


def main() -> None:
    n = 5
    big = 10 ** 12
    f = 0.5
    nan = float("nan")
    s = "text"
    xs = [1, 2]
    zero = 0.0
    one = 1
    items: list[object] = [n, big, f, nan, True, s, xs, None, MARK, -0.0]
    for x in items:
        print(x is None, x is not None, x is MARK, x is n, x is big, x is f, x is nan, x is True, x is False, x is s, x is xs, x is zero)
    a: object = n
    b: object = a
    c: object = 5
    print(a is b, a is c, b is not c, a is items[0], items[0] is items[1])
    m: int | None = 5
    print(a is m, items[7] is m)
    m = None
    print(a is m, items[7] is m)
    u: int | str = "text"
    print(items[5] is u, a is u)
    d: object = 0.0
    print(d is items[9], items[3] is items[3], d is zero)
    print(items[8] is Mark, items[6] is not xs, items[4] is items[4], items[4] is one)


main()
