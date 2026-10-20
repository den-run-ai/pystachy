# error: opt_isinstance_union_tuple.py:6: error: isinstance() is only supported with the builtin types and classes as its second argument
# A union of a type and a tuple raises TypeError (unsupported operand type(s) for |: 'type' and 'tuple')


def f(x: str | None) -> bool:
    return isinstance(x, str | (int, type(None)))


print(f(None))
