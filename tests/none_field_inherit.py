# A base's field first None, given an object by a subclass's method: one field of both.
class Base:
    def __init__(self) -> None:
        self.peer = None

    def has_peer(self) -> bool:
        return self.peer is not None


class Child(Base):
    def link(self, other: "Child") -> None:
        self.peer = other


a = Child()
b = Child()
print(a.has_peer(), b.has_peer())
a.link(b)
print(a.has_peer(), a.peer is b)
x: Base = a
print(x.peer is b, x.has_peer())
