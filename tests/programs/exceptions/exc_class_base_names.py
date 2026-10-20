# An exception class's base may be named IOError or EnvironmentError (OSError), builtins.X or os.error.
import builtins
import os


class A(builtins.ValueError):
    pass


class B(os.error):
    pass


class C(EnvironmentError):
    pass


class D(IOError):
    def __init__(self, m: str) -> None:
        super().__init__(m)


print(repr(A("a")), repr(A("b")))
try:
    raise A("a")
except ValueError as e:
    print("ValueError", repr(e))
try:
    raise B("b")
except OSError as e:
    print(repr(e), str(e))
try:
    raise C("c")
except IOError as e:
    print(repr(e), type(e).__name__)
try:
    raise D("d")
except EnvironmentError as e:
    print(repr(e), isinstance(e, OSError))
raise D("uncaught")
