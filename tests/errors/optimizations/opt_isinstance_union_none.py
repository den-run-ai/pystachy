# error: opt_isinstance_union_none.py:6: error: isinstance() is only supported with the builtin types and classes as its second argument
# None | None raises TypeError (unsupported operand type(s) for |: 'NoneType' and 'NoneType')


def f(x: int | None) -> bool:
    return isinstance(x, None | None)


print(f(None))
