# Each comparison site below meets None and an object of every class of a hierarchy, on
# either side. Pairs whose comparison calls one method share code (#625), so each pair must
# still call the method CPython calls, on the operand CPython calls it on; the others compare
# identities or raise TypeError.
class Base:
    def __init__(self, name: str, n: int) -> None:
        self.name = name
        self.n = n

    def __eq__(self, other: "Base | None") -> bool:
        print("  Base.__eq__", self.name, other.name if other is not None else None)
        return other is not None and self.n == other.n

    def __lt__(self, other: "Base | None") -> bool:
        print("  Base.__lt__", self.name, other.name if other is not None else None)
        return other is not None and self.n < other.n


class Left(Base):
    pass


class Right(Base):
    def __eq__(self, other: "Base | None") -> bool:
        print("  Right.__eq__", self.name, other.name if other is not None else None)
        return other is not None and self.n % 10 == other.n % 10

    def __gt__(self, other: "Base | None") -> bool:
        print("  Right.__gt__", self.name, other.name if other is not None else None)
        return other is not None and self.n > other.n


class Deep(Left):
    pass


def eq(a: Base | None, b: Base | None) -> bool:
    return a == b


def ne(a: Base | None, b: Base | None) -> bool:
    return a != b


def lt(a: Base | None, b: Base | None) -> bool:
    return a < b


def gt(a: Base | None, b: Base | None) -> bool:
    return a > b


def label(x: Base | None) -> str:
    return x.name if x is not None else "None"


xs: list[Base | None] = [None, Base("b", 1), Left("l", 11), Right("r", 21), Deep("d", 1)]
for x in xs:
    for y in xs:
        print(label(x), label(y))
        print(" ==", eq(x, y))
        print(" !=", ne(x, y))
        try:
            print(" <", lt(x, y))
        except TypeError as e:
            print(" < TypeError:", e)
        try:
            print(" >", gt(x, y))
        except TypeError as e:
            print(" > TypeError:", e)


class Plain:
    pass


class Sub(Plain):
    pass


def same(a: Plain | None, b: Plain | None) -> bool:
    return a == b


def other(a: Plain | None, b: Plain | None) -> bool:
    return a != b


ps: list[Plain | None] = [None, Plain(), Sub(), Sub()]
for p in ps:
    print([same(p, q) for q in ps], [other(p, q) for q in ps])


class Problem(Exception):
    def __eq__(self, other: object) -> bool:
        print("  Problem.__eq__", str(self), str(other) if isinstance(other, Problem) else "None")
        return isinstance(other, Problem) and str(self)[0] == str(other)[0]


class Minor(Problem):
    pass


class Major(Problem):
    pass


class Fatal(Major):
    pass


def peq(a: Problem | None, b: Problem | None) -> bool:
    return a == b


def pne(a: Problem | None, b: Problem | None) -> bool:
    return a != b


es: list[Problem | None] = [None, Problem("p1"), Minor("m1"), Major("M1"), Fatal("f1"), Minor("p2")]
for u in es:
    for w in es:
        print(str(u), str(w), peq(u, w), pne(u, w))
