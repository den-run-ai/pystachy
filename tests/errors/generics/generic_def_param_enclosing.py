# error: generic_def_param_enclosing.py:7: error: TypeVar 'T' cannot be used as a value (only annotations may name it)
# (CPython raises TypeError: unsupported operand type(s) for +: 'typing.TypeVar' and 'int': the type parameter hides outer()'s T)
def outer() -> int:
    T = 5

    def inner[T](y: T) -> int:
        return T + 1

    return inner(1)


print(outer())
