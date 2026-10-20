# Numeric exponents dispatch without changing their type. Power can return a scalar,
# construct a new object, or mutate and preserve identity through __ipow__.
class Power:
    def __init__(self, data: float) -> None:
        self.data = data

    def __pow__(self, exponent, modulus=None):
        if modulus is not None:
            return Power(self.data + modulus)
        return Power(self.data ** exponent)


class Kind:
    def __pow__(self, exponent):
        if isinstance(exponent, bool):
            return "bool"
        if isinstance(exponent, int):
            return "int"
        return "float"


class Mutable:
    def __init__(self, data: float) -> None:
        self.data = data

    def __ipow__(self, exponent):
        print("ipow", exponent)
        self.data **= exponent
        return self

    def __pow__(self, exponent: float) -> "Mutable":
        print("pow", exponent)
        return Mutable(self.data ** exponent)


print((Power(4.0) ** 2).data, (Power(4.0) ** -0.5).data, pow(Power(4.0), True).data)
print(Kind() ** True, pow(Kind(), 2), Kind() ** 0.5)
print(Power(4.0).__pow__(2, 3).data)
p = Power(3.0)
old = p
p **= 2
print(p.data, old.data, p is old)
m = Mutable(3.0)
alias = m
m **= 2
print(m.data, m is alias)
print((m ** 0.5).data, m.data)


class Base:
    def __init__(self, data: float) -> None:
        self.data = data

    def __pow__(self, exponent: float) -> float:
        return self.data ** exponent


class Inherited(Base):
    pass


class Override(Base):
    def __pow__(self, exponent: float) -> float:
        return 10.0 + self.data ** exponent


def apply(value: Base) -> float:
    return value ** 2.0


print(apply(Base(3.0)), apply(Inherited(3.0)), apply(Override(3.0)))


class InplaceBase:
    def __init__(self, data: float) -> None:
        self.data = data

    def __ipow__(self, exponent: int) -> "InplaceBase":
        self.data **= exponent
        return self


class InplaceOverride(InplaceBase):
    def __ipow__(self, exponent: int) -> InplaceBase:
        self.data = 10.0 + self.data ** exponent
        return self


def apply_inplace(value: InplaceBase) -> float:
    value **= 2
    return value.data


print(apply_inplace(InplaceBase(3.0)), apply_inplace(InplaceOverride(3.0)))


def maybe(present: bool) -> Power:
    if present:
        return Power(2.0)
    return None


def exponent() -> int:
    print("exponent")
    return 2


none = maybe(False)
try:
    print((none ** exponent()).data)
except TypeError as error:
    print(error)
try:
    print(pow(none, exponent()).data)
except TypeError as error:
    print(error)
try:
    none **= exponent()
except TypeError as error:
    print(error)
try:
    print((Power(0.0) ** -1).data)
except ZeroDivisionError as error:
    print(error)


class Grid:
    def __init__(self) -> None:
        self.cells = [Mutable(2.0)]

    def __getitem__(self, index: int) -> Mutable:
        print("get", index)
        return self.cells[index]

    def __setitem__(self, index: int, value: Mutable) -> None:
        print("set", index)
        self.cells[index] = value


def index() -> int:
    print("index")
    return 0


g = Grid()
g[index()] **= exponent()
print(g.cells[0].data)
