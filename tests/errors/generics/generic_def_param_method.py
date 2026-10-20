# error: generic_def_param_method.py:8: error: TypeVar 'U' cannot be used as a value (only annotations may name it)
# (CPython prints U: a generic method's type parameter is a TypeVar in its body too)
class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def show[U](self, u: U) -> int:
        print(U)
        return self.v


print(Box(1).show("a"))
