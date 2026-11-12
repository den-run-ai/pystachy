# error: cannot infer the type of field 'kind'; annotate it (self.kind: T = ...)
# A class declared further down types no field of an earlier class.
class Op:
    def __init__(self) -> None:
        self.kind = Branch.BOOL


class Branch:
    BOOL = 100


print(Op().kind)
