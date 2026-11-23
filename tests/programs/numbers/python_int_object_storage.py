# pystachy: python-int
# a promoting int stored as object keeps its value past 64 bits: printed, compared (with the 64-bit
# ints, bools, floats and other values stored beside it), hashed, tested by isinstance() and 'is'
def main() -> None:
    big = 2 ** 70
    five = 5
    xs: list[object] = [big, 5, -1, True, "s", None, 2.5]
    for x in xs:
        print(x, repr(x), x == big, x == 5, hash(x) == hash(5), x is None, f"{x}")
    print(xs[0] == 2 ** 70, 2 ** 70 == xs[0], xs[1] == 5.0, xs[3] == 1, xs[0] is big, xs[1] is five)
    o: object = big * big
    print(o, isinstance(o, int), isinstance(o, bool), isinstance(xs[3], int), hash(o) == hash(big * big))
    print(o == xs[0], xs[0] != o, o == big * big, type(o).__name__)


main()
