# A secondary base whose own base is no class of the primary chain is no trait: it is an
# interface that extends another (Statement's base Other is no base of FuncBase), whose methods
# the class inherits as a root secondary base's.
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
