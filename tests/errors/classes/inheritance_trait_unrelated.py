# error: inheritance_trait_unrelated.py:17: error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base, or several
# A secondary base with bases must reach a class of the primary chain: here Statement's base
# Other is no base of FuncBase.
class Other:
    pass


class Statement(Other):
    def kind(self) -> str:
        return "statement"


class FuncBase:
    pass


class FuncDef(FuncBase, Statement):
    pass


print(FuncDef().kind())
