# error: isinstance_tuple_call.py:11: error: isinstance() is only supported with the builtin types and classes as its second argument
# CPython builds the whole tuple before isinstance() tests its items: later() runs although the test
# stops at int


def later() -> int:
    print("later")
    return 5


print(isinstance(1, (int, later())))
