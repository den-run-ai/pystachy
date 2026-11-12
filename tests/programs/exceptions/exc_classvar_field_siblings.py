# A base-typed read selects the actual exception class's mutable default, including
# independently shadowed sibling defaults and deep inheritance, until an instance write.
class Base(Exception):
    def __init__(self) -> None:
        super().__init__("base")
        self.label = "base"

    def show(self) -> str:
        return self.label.upper()


class Sub(Base):
    label = "sub"

    def __init__(self) -> None:
        pass


class Deep(Sub):
    pass


class Grand(Deep):
    pass


class Other(Base):
    label = "other"

    def __init__(self) -> None:
        pass


def view(b: Base) -> str:
    return b.label


def assign(b: Base, text: str) -> None:
    b.label = text


s = Sub()
d = Deep()
g = Grand()
o = Other()
print(view(s), view(d), view(g), view(o))
Sub.label = "sub changed"
Other.label = "other changed"
print(s.show(), d.show(), g.show(), o.show())
assign(g, "own")
Sub.label = "sub again"
print(view(s), view(d), view(g), view(o))
