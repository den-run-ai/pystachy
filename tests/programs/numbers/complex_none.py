# a complex | None that holds None, whose object is a null pointer: arithmetic raises CPython's
# TypeError naming NoneType (on either side, also both), == and != compare it with None's
# identity, and complex() of it raises its TypeError, as CPython's do
def get(flag: bool) -> complex | None:
    return 1j if flag else None


def show(label: str, f) -> None:
    try:
        print(label, f())
    except TypeError as e:
        print(label, "TypeError:", e)


x = get(False)
y = get(True)
show("add", lambda: x + 1)
show("radd", lambda: 2.5 - x)
show("mul", lambda: x * 2j)
show("pow", lambda: x ** x)
show("iadd", lambda: y + x)
show("eq", lambda: (x == 1, x != 1j, 1j == x, x == x, x == y, y != x))
show("complex", lambda: complex(x))
show("complex2", lambda: complex(1, x))
show("values", lambda: (y + 1, y == 1j, y == 1, complex(y), x))
