# A tuple[A, ...] (or of a subclass of A) where a tuple[A | B, ...] is wanted converts: a new tuple
# of the items' union boxes, which an argument, an annotated variable and a concatenation take
class A:
    def __init__(self, n: int) -> None:
        self.n = n

    def name(self) -> str:
        return f"A{self.n}"


class B:
    def name(self) -> str:
        return "B"


class SubA(A):
    def name(self) -> str:
        return f"SubA{self.n}"


def names(items: tuple[A | B, ...] | None) -> list[str]:
    out: list[str] = []
    if items is not None:
        for x in items:
            out.append(x.name())
    return out


def build(ns: list[int]) -> tuple[A, ...]:
    return tuple(A(n) for n in ns)


aa = build([1, 2])
print(names(aa), names(build([])), names(None))
subs: tuple[SubA, ...] = (SubA(3), SubA(4))
print(names(subs))
widened: tuple[A | B, ...] = aa
print(len(widened), names(widened + (B(),)))
