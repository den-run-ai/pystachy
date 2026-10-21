# error: generic_def_param_body.py:7: error: TypeVar 'T' cannot be used as a value (only annotations may name it)
# (CPython raises TypeError: unsupported operand type(s) for +: 'typing.TypeVar' and 'int': the type parameter hides the module's T)
T = 5


def f[T](x: T) -> int:
    return T + 1


print(f(1))
