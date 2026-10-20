# error: isinstance_not_type.py:7: error: isinstance() is only supported with the builtin types and classes as its second argument
# CPython tests a tuple's items in order: 5, before int, raises TypeError (isinstance() arg 2 must
# be a type, a tuple of types, or a union)


def f(n: int) -> bool:
    return isinstance(n, (5, int))


print(f(1))
