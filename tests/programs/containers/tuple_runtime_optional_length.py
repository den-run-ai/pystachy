# The length of a tuple[str, ...] | None field, read after its None test in a function that also
# narrows a union: the IR check's union proof does not take the tuple's length word for a union's
# tag, which would need a nonnull proof the field read cannot give
class A:
    def __init__(self, name: str) -> None:
        self.name = name


class B:
    def __init__(self, path: str) -> None:
        self.path = path


class P:
    def __init__(self, item: A | B, names: tuple[str, ...] | None = None) -> None:
        self.label = "p"
        self.item = item
        self.names = names


def make(xs: list[str]) -> tuple[str, ...]:
    return tuple(xs)


def show(p: P) -> None:
    item = p.item
    if isinstance(item, A):
        print("a", item.name)
    else:
        print("b", item.path)
    if p.names is None:
        print("none")
        return
    print(p.label, len(p.names))


show(P(A("x"), make(["n"])))
show(P(B("y.c")))
