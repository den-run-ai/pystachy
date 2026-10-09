# error: exception_optional_class.py:2: error: an exception that may be None (ValueError | None) is not supported: only an object of an exception class of the program may be None
def f(e: ValueError | None) -> None:
    print(e)


f(None)
