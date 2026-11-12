# error: inheritance_trait_field.py:20: error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base, or several
# A trait (a secondary base derived from a class of the primary chain) may add no fields: a
# method that stores to the instance would give its objects another layout.
class Node:
    def __init__(self) -> None:
        self.line = 1


class Statement(Node):
    def mark(self) -> None:
        self.done = True


class FuncBase(Node):
    def __init__(self) -> None:
        super().__init__()
        self.name = "f"


class FuncDef(FuncBase, Statement):
    pass


print(FuncDef().name)
