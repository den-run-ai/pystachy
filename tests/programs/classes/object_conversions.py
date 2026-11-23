# the operations of a value of object whose result has one type whatever it holds, which
# isinstance() need not narrow: len(), int(), float() and the numeric conversions of %
# formatting, each by the type it holds, with CPython's TypeError for a type that has no such
# conversion (and None), its ValueError and OverflowError, a class's __len__, __int__, __float__ and
# __index__, and bytes by their ASCII text
class Sized:
    def __len__(self) -> int:
        return 3


class Num:
    def __int__(self) -> int:
        return 7

    def __float__(self) -> float:
        return 7.5

    def __index__(self) -> int:
        return 8


class Plain:
    pass


def attempt(label: str, f: int, v: object) -> None:
    x: object = v
    try:
        if f == 0:
            print(label, "len", len(x))
        elif f == 1:
            print(label, "int", int(x))
        elif f == 2:
            print(label, "float", float(x))
        elif f == 3:
            print(label, "%d", "%d|%5d|%-4d|%+d" % (x, x, x, x))
        elif f == 4:
            print(label, "%x", "%x %X %o %#x" % (x, x, x, x))
        elif f == 5:
            print(label, "%f", "%.2f %e %g" % (x, x, x))
        else:
            print(label, "%c", "[%c]" % x)
    except (TypeError, ValueError, OverflowError) as e:
        print(label, type(e).__name__, e)


def main() -> None:
    values: list[object] = [3, True, 2.5, "12", "x", b"34", b"\xff", [1, 2], {"a": 1}, (1,), {1}, None, Sized(), Num(), Plain(), float("inf"), 65, "A", "", frozenset()]
    for i in range(len(values)):
        for f in range(7):
            attempt(str(i), f, values[i])


main()
