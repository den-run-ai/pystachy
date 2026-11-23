# A Protocol value is its object: identity, printing and truth are the object's own.
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class Plain:
    def name(self) -> str:
        return "plain"


class Shown:
    def __init__(self, n: int) -> None:
        self.n = n

    def name(self) -> str:
        return "shown"

    def __repr__(self) -> str:
        return f"Shown({self.n})"

    def __str__(self) -> str:
        return f"<{self.n}>"


class Empty:
    def __init__(self, size: int) -> None:
        self.size = size

    def name(self) -> str:
        return "empty"

    def __len__(self) -> int:
        return self.size


shown = Shown(3)
a: Named = shown
b: Named = shown
c: Named = Shown(3)
print(a is b, a is not b, a is shown, a is c, c is not shown)
print(a, repr(a), str(a), f"{a}", [a, c])
print(bool(Empty(0)), bool(Empty(2)))
e: Named = Empty(0)
f: Named = Empty(1)
print(bool(e), bool(f), not e, "yes" if f else "no")
none: Named | None = None
print(none is None, none is not None)
maybe: Named | None = Plain()
if maybe is not None:
    print(maybe.name())
values: list[Named] = [shown, Plain(), shown]
print(values[0] is values[2], values[0] is values[1])
print(sum(1 for v in values if v is shown))
