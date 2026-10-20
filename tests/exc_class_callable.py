# A class object is callable, as CPython's callable() says: a class named, one held as a value, and
# one that may be None (callable unless it is None)


class E(Exception):
    pass


def check(c: type[BaseException] | None, d: type[BaseException]) -> None:
    print(callable(c), callable(d))
    if callable(c):
        print("calls", repr(c()))


print(callable(ValueError), callable(E))
check(None, KeyError)
check(E, E)
check(KeyError, ValueError)
try:
    raise OSError("o")
except OSError as e:
    print(callable(type(e)))
