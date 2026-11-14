# A field stored from a field of a parameter whose class the module declares later infers that
# class's fields first, and its bases' before them, in their declaration order: Derived's slots
# extend Base's, and Owner's fields take the types of fields from both.
class Owner:
    def __init__(self, p: "Derived") -> None:
        self.size = p.size
        self.base = p.a


class Base:
    __slots__ = ("a",)

    def __init__(self) -> None:
        self.a = "base"


class Derived(Base):
    __slots__ = ("size",)

    def __init__(self) -> None:
        super().__init__()
        self.size = 3


o = Owner(Derived())
print(o.size + 1, o.base.upper())
