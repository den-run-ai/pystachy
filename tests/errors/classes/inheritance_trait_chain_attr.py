# error: inheritance_trait_chain_attr.py:23: error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base, or several
# A trait derives from a class of the primary base's chain directly: a class between them, here
# with a class attribute (x, which CPython reads as 100), would need storage that the objects of a
# class deriving from both lay out as the primary base's (y).
class Root:
    pass


class Primary(Root):
    def __init__(self) -> None:
        self.y = 5


class Ancestor(Root):
    x = 100


class Trait(Ancestor):
    def m(self) -> int:
        return 1


class Both(Primary, Trait):
    pass


def read(t: Trait) -> int:
    return t.x


print(read(Both()))
