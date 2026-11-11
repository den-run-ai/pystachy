# error: an except clause's class object may be None, for which CPython raises TypeError: test that it is not None before the try statement
# A clause that takes a class object needs one that is never None: CPython raises TypeError
# where it tests None, before any class of a tuple (tests/programs/exceptions/except_class_values.py)
def f(kind: type[BaseException] | None) -> None:
    try:
        int("x")
    except kind:
        print("caught")


f(ValueError)
