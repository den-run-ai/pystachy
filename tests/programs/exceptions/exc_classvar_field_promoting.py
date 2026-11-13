# pystachy: python-int
# Shared flags and fallback selection keep both words of a promoting integer field.
class Base(Exception):
    def __init__(self) -> None:
        super().__init__("base")
        self.value = 2**90


class Sub(Base):
    value = 2**100

    def __init__(self) -> None:
        pass


def view(b: Base) -> int:
    return b.value


def assign(b: Base, n: int) -> None:
    b.value = n


Sub.value = 2**105
b = Sub()
print(view(b), view(Base()))
assign(b, 2**110)
print(view(b), view(Sub()))
