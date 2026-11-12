# Every binary reflected spelling keeps the original operand order.
class Reflected:
    def __init__(self, value: int) -> None:
        self.value = value

    def __radd__(self, other: int) -> int:
        return other + self.value

    def __rsub__(self, other: int) -> int:
        return other - self.value

    def __rmul__(self, other: int) -> int:
        return other * self.value

    def __rtruediv__(self, other: int) -> float:
        return other / self.value

    def __rfloordiv__(self, other: int) -> int:
        return other // self.value

    def __rmod__(self, other: int) -> int:
        return other % self.value

    def __rmatmul__(self, other: int) -> int:
        return other * 100 + self.value

    def __rand__(self, other: int) -> int:
        return other & self.value

    def __ror__(self, other: int) -> int:
        return other | self.value

    def __rxor__(self, other: int) -> int:
        return other ^ self.value

    def __rlshift__(self, other: int) -> int:
        return other << self.value

    def __rrshift__(self, other: int) -> int:
        return other >> self.value

    def __rpow__(self, other: int) -> int:
        return other ** self.value

    def __rdivmod__(self, other: int) -> tuple[int, int]:
        return divmod(other, self.value)


r = Reflected(3)
print(14 + r, 14 - r, 14 * r, 14 / r, 14 // r, 14 % r, 14 @ r)
print(14 & r, 14 | r, 14 ^ r, 14 << r, 14 >> r, 14 ** r, pow(14, r), divmod(14, r))


class Base:
    def __add__(self, other: object) -> str:
        print("Base.add")
        return "forward"

    def __radd__(self, other: object) -> str:
        print("Base.radd")
        return "reflected"


class Inherited(Base):
    pass


class Override(Base):
    def __radd__(self, other: object) -> str:
        print("Override.radd")
        return "subclass"


def combine(left: Base, right: Base) -> str:
    return left + right


print(combine(Base(), Inherited()))
print(combine(Base(), Override()))
print(combine(Override(), Base()))
print(combine(Override(), Override()))


class OnlyReflected:
    def __rand__(self, other: object) -> int:
        print("unexpected reflected")
        return 99


try:
    print(OnlyReflected() & OnlyReflected())
except TypeError as error:
    print(error)


class Box:
    def __init__(self, value):
        self.value = value

    def __radd__(self, other: object) -> int:
        print("unexpected template reflected")
        return 100


try:
    print(Box(1) + Box("x"))
except TypeError as error:
    print(error)


class Power:
    def __pow__(self, other: "Power") -> int:
        return 17


print(Power() ** Power(), pow(Power(), Power()))


class Formatted:
    def __str__(self) -> str:
        return "formatted"

    def __rmod__(self, other: str) -> str:
        return "unexpected reflected formatting"


print("value=%s" % Formatted())
