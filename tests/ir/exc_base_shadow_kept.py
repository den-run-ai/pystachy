# Only an unshadowed base initializer permits eliding constructor argument formatting.
class Base(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(x)


class Shadowed(Base):
    def __init__(self, Base: int, doc: str) -> None:
        self.doc = doc
        Base.__init__(self, 99)


class Forwarded(Base):
    def __init__(self, x: int, doc: str) -> None:
        self.doc = doc
        Base.__init__(self, x)


def kept(doc: str) -> Shadowed:
    return Shadowed(5, doc)


def elided(doc: str) -> Forwarded:
    return Forwarded(5, doc)


print(kept("x"), elided("y"))
