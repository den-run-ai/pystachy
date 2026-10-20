# error: opt_isinstance_tuple_call.py:11: error: isinstance() is only supported with the builtin types and classes as its second argument
# None is a type(None), the first item, but CPython has called later() to build the tuple before
# isinstance() tests it


def later() -> int:
    print("later")
    return 5


print(isinstance(None, (type(None), later())))
