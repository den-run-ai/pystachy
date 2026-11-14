# error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base, or several
# An interface may extend another that declares attributes, not one with a constructor.
class Core:
    def __init__(self) -> None:
        self.name = "core"


class Shared(Core):
    def show(self) -> str:
        return "s"


class Base:
    pass


class C(Base, Shared):
    pass
