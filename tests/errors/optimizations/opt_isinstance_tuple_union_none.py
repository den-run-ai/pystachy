# error: opt_isinstance_tuple_union_none.py:8: error: isinstance() is only supported with the builtin types and classes as its second argument
# None | None raises TypeError (unsupported operand type(s) for |: 'NoneType' and 'NoneType') as the
# tuple is built, before the test stops at type(None) for x None: the static types decide this if's
# test (f is a template) only where building the tuple does nothing


def f(x):
    if isinstance(x, (type(None), None | None)):
        print("None")


f(None)
