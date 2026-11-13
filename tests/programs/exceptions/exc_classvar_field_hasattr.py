# Probe the shared field flag without any field read that might register the subclass's
# fallback first. Missing base fields remain missing; inherited class defaults exist.
class Base(Exception):
    def __init__(self, assigned: bool) -> None:
        super().__init__("base")
        if assigned:
            self.label = "base"


class Sub(Base):
    label = "sub"

    def __init__(self) -> None:
        pass


class Deep(Sub):
    pass


class Plain(Base):
    pass


def present(b: Base) -> bool:
    return hasattr(b, "label")


def assign(b: Base) -> None:
    b.label = "own"


Sub.label = "changed"
print(present(Sub()), present(Deep()), present(Base(True)))
print(present(Base(False)), present(Plain(False)))
b = Base(False)
print(present(b))
assign(b)
print(present(b))
