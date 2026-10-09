# error: field_none.py:10: error: cannot infer the type of field 'x'; annotate it (self.x: T = ...)
# A field assigned the result of a function that returns None: a field's type is a value
# type, so this asks for an annotation (it once gave the field the type None, which LLVM rejects).
def setup() -> None:
    print("setup")


class A:
    def __init__(self) -> None:
        self.x = setup()
        self.n = 1


a = A()
print(a.x, a.n)
