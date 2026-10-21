# error: syntax_typevar_bound_walrus.py:2: error: named expression cannot be used within a TypeVar bound
def f[T: (x := int)](a: T) -> T:
    return a
