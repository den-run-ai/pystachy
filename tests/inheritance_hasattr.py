# Base-typed hasattr checks use the concrete class, including unset derived fields.
class Base:
    def __init__(self, assigned: bool = True) -> None:
        if assigned:
            self.parent = 1


class Child(Base):
    def __init__(self, assigned: bool = True) -> None:
        super().__init__(assigned)
        if assigned:
            self.child = 2

    def extra(self) -> int:
        return 3

    def __bool__(self) -> bool:
        return True


class Default(Base):
    parent = 4


def check(obj: Base) -> None:
    print(hasattr(obj, "parent"), hasattr(obj, "child"), hasattr(obj, "extra"), hasattr(obj, "__bool__"))
    if hasattr(obj, "extra"):
        print("extra present")
    if hasattr(obj, "child"):
        print("child present")


check(Base())
check(Child())
check(Child(False))
check(Default(False))
check(None)
# A mutated subclass default must not imply an unassigned base field is present.
Default.parent = 5
check(Base(False))
check(Default(False))
