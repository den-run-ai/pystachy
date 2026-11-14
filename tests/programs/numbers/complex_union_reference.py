# Beside only objects of classes, a complex number is a reference member, as in a union of classes:
# complex | C compiles, narrows by isinstance() and holds None where it may.
class C:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"C({self.n})"


def show(x: complex | C) -> None:
    if isinstance(x, complex):
        print("complex", x, x.real, x.imag, x * 2)
    else:
        print("C", x.n, x)
    print(str(x), f"{x}", format(x), x is None)


def maybe(x: complex | C | None) -> str:
    if x is None:
        return "none"
    if isinstance(x, C):
        return f"C {x.n}"
    return f"complex {x + 1}"


show(2j)
show(complex(1, -1))
show(C(3))
print(maybe(None), maybe(1 + 2j), maybe(C(4)))
xs: list[complex | C] = [1j, C(5)]
for x in xs:
    show(x)
    print(maybe(x))
