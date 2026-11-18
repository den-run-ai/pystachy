# error: cannot infer the type of field 'kind'; annotate it (self.kind: T = ...)
# A local with the class's name hides it: the field is not typed by the class's attribute.
class Branch:
    BOOL = 100


class Label:
    def __init__(self) -> None:
        self.BOOL = "bool"


class Op:
    def __init__(self) -> None:
        Branch = Label()
        self.kind = Branch.BOOL


print(Op().kind)
