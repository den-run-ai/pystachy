# error: opt_isinstance_tuple_none.py:7: error: isinstance() is only supported with the builtin types and classes as its second argument
# None in a tuple of types is no type: CPython raises TypeError where the test reaches it, here
# when x is None (in a union, None is NoneType)


def f(x: int | None) -> bool:
    return isinstance(x, (int, None))


print(f(1), f(None))
