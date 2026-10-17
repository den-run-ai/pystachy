# error: **= through Base may call Child.__ipow__; use the concrete receiver type
class Base:
    def __pow__(self, exponent: int) -> "Base":
        print("base pow")
        return self


class Child(Base):
    def __ipow__(self, exponent: int) -> "Child":
        print("child ipow")
        return self


def apply(value: Base) -> Base:
    value **= 2
    return value


apply(Child())
