# __getattr__ (#1536) where a derived class's __init__ does not call its base's: the base's fields
# are unassigned in its objects, so a read of one asks the method, as in CPython, until the program
# assigns the field. Here the method's value is one of each field's type (else: tests/errors).
class Base:
    def __init__(self) -> None:
        self.size = 1
        self.depth = 2

    def __getattr__(self, name: str) -> int:
        if name == "depth":
            raise AttributeError(f"no {name} yet")
        return -len(name)

    def area(self) -> int:
        return self.size * 10


class Careful(Base):
    count: int

    def __init__(self) -> None:
        self.label = 5


def show(b: Base) -> None:
    print(b.size, b.area(), hasattr(b, "depth"), getattr(b, "depth", 0), getattr(b, "size", 0))


k = Careful()
print(k.label, k.size, k.count, k.port, hasattr(k, "count"), hasattr(k, "size"))
show(Base())
show(k)
try:
    print(k.depth)
except AttributeError as e:
    print("AttributeError:", e)
k.size = 3
k.count = 8
k.depth = 4
show(k)
print(k.size, k.count, k.depth, hasattr(k, "depth"))
