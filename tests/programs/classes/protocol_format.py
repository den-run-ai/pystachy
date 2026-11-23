# A Protocol value formats as its object does: f-strings, format() and str.format() call the
# object's class's __format__ (str() for an empty spec where it has none), print() its __str__.
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class Plain:
    def name(self) -> str:
        return "plain"

    def __str__(self) -> str:
        return "Plain!"

    def __repr__(self) -> str:
        return "Plain()"


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def name(self) -> str:
        return "money"

    def __format__(self, spec: str) -> str:
        print("Money.__format__", repr(spec))
        if spec == "":
            return f"{self.cents // 100}.{self.cents % 100:02d}"
        return f"[{spec}:{self.cents}]"

    def __repr__(self) -> str:
        return f"Money({self.cents})"


def show(x: Named, spec: str) -> str:
    return f"<{x:{spec}}>"


xs: list[Named] = [Plain(), Money(1234)]
for x in xs:
    print(f"{x}", f"{x!r}", f"{x!s}", format(x), str(x), repr(x))
    print(x, [x], (x, 1))
m: Named = Money(5)
print(f"{m:>8}", format(m, "x"), "{}".format(m), "{:q}".format(m), show(m, "w"))
p: Named = Plain()
print(show(p, ""))
try:
    print(f"{p:>8}")
except TypeError as e:
    print("TypeError:", e)
try:
    print(show(p, "z"))
except TypeError as e:
    print("TypeError:", e)
n: Named | None = None
print(f"{n}", format(n), str(n), repr(n), "{}".format(n))
try:
    print(format(n, "x"))
except TypeError as e:
    print("TypeError:", e)
