# Power methods bind an already evaluated exponent through normal positional arguments.
class Variadic:
    def __pow__(self, *args, modulus=7):
        print("power", args, modulus)
        return len(args)


class Typed:
    def __pow__(self, *args: float) -> float:
        print("typed", args)
        return sum(args)


class Inplace:
    def __init__(self) -> None:
        self.count = 0

    def __ipow__(self, *args):
        print("inplace", args)
        self.count = len(args)
        return self


class TypedInplace:
    def __init__(self) -> None:
        self.count = 0

    def __ipow__(self, *args: int) -> "TypedInplace":
        print("typed inplace", args)
        self.count = len(args)
        return self


def exponent() -> int:
    print("exponent")
    return 2


print(Variadic() ** exponent(), pow(Variadic(), True))
print(Typed() ** 0.5, pow(Typed(), 2.0))
value = Inplace()
value **= exponent()
print(value.count)
typed = TypedInplace()
typed **= exponent()
print(typed.count)


class Base:
    def __pow__(self, exponent: float) -> float:
        return exponent


class Child(Base):
    def __pow__(self, *args: float) -> float:
        return sum(args)


def apply(value: Base) -> float:
    return value ** 0.5


print(apply(Base()), apply(Child()))
