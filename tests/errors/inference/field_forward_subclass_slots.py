# error: field_forward_subclass_slots.py:23: error: field 'extra' is outside __slots__ of 'Derived' (compiling Derived.__init__() for the call at
# A field stored from a field of a parameter whose class the module declares later infers that
# class's fields first, and its base's before them: Derived's slots extend Base's, so a field
# outside both is an error (CPython's AttributeError when Derived() runs).
class Owner:
    def __init__(self, p: "Derived") -> None:
        self.size = p.size


class Base:
    __slots__ = ("a",)

    def __init__(self) -> None:
        self.a = 1


class Derived(Base):
    __slots__ = ("size",)

    def __init__(self) -> None:
        super().__init__()
        self.size = 3
        self.extra = 7


print(Owner(Derived()).size)
