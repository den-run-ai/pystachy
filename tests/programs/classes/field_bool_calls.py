# A field whose value is a call of any(), all(), callable(), isinstance() or hasattr() is a bool,
# whatever the arguments (mypyc's PrimitiveDescription.is_ambiguous = any(...) of a generator)
class Base:
    def f(self) -> int:
        return 1


class Leaf(Base):
    pass


class Desc:
    def __init__(self, xs: list[int], o: Base) -> None:
        self.amb = any(x > 2 for x in xs)
        self.every = all(x > 0 for x in xs)
        self.call = callable(o)
        self.leaf = isinstance(o, Leaf)
        self.has = hasattr(o, "f")


for d in [Desc([1, 3], Leaf()), Desc([], Base())]:
    print(d.amb, d.every, d.call, d.leaf, d.has, type(d.amb).__name__, d.amb + d.every + 1)
