# A union of objects and scalars is used without narrowing where each member has the operation:
# arithmetic (an object's method, the reflected one for a number on its left), comparisons,
# truth, str(), repr(), format() and the conversions select the member's own by the box's tag.
# None, which such a union may hold as a class's value may, raises CPython's errors.
import math


class Amount:
    def __init__(self, units: int) -> None:
        self.units = units

    def __repr__(self) -> str:
        return f"Amount({self.units})"

    def __str__(self) -> str:
        return f"{self.units}u"

    def __format__(self, spec: str) -> str:
        return "<" + format(self.units, spec) + ">"

    def __bool__(self) -> bool:
        return self.units != 0

    def __add__(self, other: "Amount | int") -> "Amount":
        if isinstance(other, Amount):
            return Amount(self.units + other.units)
        return Amount(self.units + other)

    def __radd__(self, other: int) -> "Amount":
        return Amount(1000 + self.units + other)

    def __sub__(self, other: "Amount | int") -> "Amount":
        if isinstance(other, Amount):
            return Amount(self.units - other.units)
        return Amount(self.units - other)

    def __rsub__(self, other: int) -> "Amount":
        return Amount(other - self.units)

    def __mul__(self, other: int) -> "Amount":
        return Amount(self.units * other)

    def __rmul__(self, other: int) -> "Amount":
        return Amount(self.units * other)

    def __truediv__(self, other: int) -> float:
        return self.units / other

    def __neg__(self) -> "Amount":
        return Amount(-self.units)

    def __abs__(self) -> "Amount":
        return Amount(abs(self.units))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Amount):
            return self.units == other.units
        if isinstance(other, int):
            return self.units == other
        return False

    def __lt__(self, other: "Amount | int") -> bool:
        if isinstance(other, Amount):
            return self.units < other.units
        return self.units < other

    def __gt__(self, other: "Amount | int") -> bool:
        if isinstance(other, Amount):
            return self.units > other.units
        return self.units > other

    def __int__(self) -> int:
        return self.units

    def __float__(self) -> float:
        return self.units + 0.5

    def __round__(self, digits: int = 0) -> int:
        return self.units + digits

    def __floor__(self) -> int:
        return self.units - 1


class Plain:
    def __init__(self, n: int) -> None:
        self.n = n


class Child(Plain):
    pass


def pick(n: int) -> "int | Amount":
    return n if n % 2 == 0 else Amount(n)


def none() -> "int | Amount":
    missing: Amount = Amount(1) if len("a") > 1 else None
    return missing


def plain(n: int) -> "int | Plain":
    return n if n % 2 == 0 else (Child(n) if n > 10 else Plain(n))


def text(n: int) -> "str | float | Amount":
    return "s" if n == 0 else 1.5 if n == 1 else Amount(n)


def arithmetic() -> None:
    a = pick(1)
    b = pick(2)
    print(a + Amount(1), b + Amount(1), a + 1, b + 1, Amount(1) + a, Amount(1) + b)
    print(a + a, b + b, a + b, b + a, a - b, b - a, a * 3, b * 3, 3 * a, a / 2, b / 2)
    print(-a, -b, abs(pick(-1)), abs(pick(-2)))
    total = pick(2)
    total += Amount(5)
    total += 1
    print(total)
    start = pick(4)
    start += 3
    print(start)


def comparisons() -> None:
    a = pick(1)
    b = pick(2)
    print(a == 1, 1 == a, a == Amount(1), a != b, b == 2, 2 == b, b != 2, a == a, a == pick(1), a == pick(3))
    print(a < pick(3), a < 2, b < pick(3), b < pick(4), a > b, pick(3) > 2, 2 < pick(3))
    p = plain(1)
    q = p
    print(p == q, p == plain(1), p != q, plain(11) == plain(11), plain(2) == plain(2), plain(2) == p, p == 2)
    kept = Plain(3)
    held: int | Plain = kept
    print(held == kept, kept == held, held != kept, held == Plain(3), held == 3, 3 == held, held == Child(3))
    print(text(0) == "s", text(1) == 1.5, text(2) == text(2), text(0) == text(1), "s" == text(0), 1.5 == text(1))


def texts() -> None:
    a = pick(1)
    b = pick(2)
    print(a, b, str(a) + "|" + str(b), repr(a), repr(b), repr(text(0)), text(1), text(2))
    print(f"{a} {b} {a!r} {a:03d} {b:03d} {a!s}", format(a, "x"), format(b, "x"), format(a), format(b))
    print("%s %r" % (a, b), ", ".join([str(a), str(b)]))
    print(bool(a), bool(b), bool(pick(0)), not a, not pick(0))
    for n in range(3):
        print("set" if pick(n) else "unset")


def conversions() -> None:
    a = pick(3)
    b = pick(4)
    print(int(a), int(b), float(a), float(b), round(a), round(b), round(a, 2), math.floor(a), math.floor(b))
    print(max(a, Amount(1)), min(b, 5), divmod(Amount(7).units, 2))


def nones() -> None:
    n = none()
    print(n is None, n, repr(n), str(n), f"{n}", bool(n), n == n, n == pick(1), pick(1) == n, n != pick(2), n == None)
    for attempt in range(8):
        try:
            if attempt == 0:
                print(n + 1)
            elif attempt == 1:
                print(1 + n)
            elif attempt == 2:
                print(n < 3)
            elif attempt == 3:
                print(n > n)
            elif attempt == 4:
                print(int(n))
            elif attempt == 5:
                print(f"{n:d}")
            elif attempt == 6:
                print(-n)
            else:
                print(abs(n))
        except TypeError as error:
            print("TypeError:", error)


arithmetic()
comparisons()
texts()
conversions()
nones()
