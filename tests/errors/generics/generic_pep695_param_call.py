# error: generic_pep695_param_call.py:12: error: TypeVar 'K' cannot be used as a value (only annotations may name it)
# (CPython raises TypeError: 'typing.TypeVar' object is not callable: the type parameter hides the def)
def K(x: int) -> int:
    return x


class C[K]:
    def __init__(self, x: K) -> None:
        self.x = x

    def f(self) -> int:
        return K(3)


print(C(1).f())
