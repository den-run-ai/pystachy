# x == o and x != o for a number or str x and an object o: the number's own __eq__ declines an
# object, so CPython asks o.__eq__(x) (o.__ne__(x) for !=, else not o.__eq__(x)); an o that is
# None equals no number. divmod(x, o) is o.__rdivmod__(x).
class Unit:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        print("  eq", self.n)
        if isinstance(other, Unit):
            return self.n == other.n
        if isinstance(other, (int, float)):
            return self.n == other
        if isinstance(other, str):
            return str(self.n) == other
        return False

    def __divmod__(self, other: int) -> tuple[int, int]:
        return divmod(self.n, other)

    def __rdivmod__(self, other: int) -> tuple[int, int]:
        print("  rdivmod", other)
        return divmod(other, self.n)


class Loud(Unit):
    def __eq__(self, other: object) -> bool:
        print("  loud eq")
        return True

    def __ne__(self, other: object) -> bool:
        print("  loud ne")
        return True


def check(u: Unit) -> None:
    print(3 == u, u == 3, 3 != u, 4 == u, 4 != u, 3.0 == u, "3" == u, True == u)


def missing() -> Unit:
    return Unit(1) if len("a") > 1 else None


check(Unit(3))
check(Loud(3))
absent = missing()
print(3 == absent, 3 != absent, "s" == absent, 1.5 != absent)
print(divmod(7, Unit(2)), divmod(Unit(7), 2))
try:
    print(divmod(7, absent))
except TypeError as error:
    print("TypeError:", error)
