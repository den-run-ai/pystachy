# raise ... from ...: the raised expression and the cause's are evaluated first, and only then are
# their classes called, the raised class first, as CPython's raise does; a cause expression that
# raises leaves the raised class uncalled, and None is raised as TypeError after the cause runs


class E(Exception):
    def __init__(self) -> None:
        print("E()")
        super().__init__("e")


class F(Exception):
    def __init__(self) -> None:
        print("F()")
        super().__init__("f")


def cause() -> BaseException:
    print("cause()")
    return KeyError("k")


def bad() -> BaseException:
    print("bad()")
    raise ValueError("bad")


def held(c: type[BaseException], d: type[BaseException] | None) -> None:
    try:
        raise c from cause()
    except Exception as x:
        print(type(x).__name__, repr(x.__cause__))
    try:
        raise c from bad()
    except ValueError as x:
        print("ValueError", x)
    try:
        raise c from d
    except Exception as x:
        print(type(x).__name__, repr(x.__cause__))


def maybe(e: BaseException | None) -> None:
    try:
        raise e from cause()
    except TypeError as x:
        print("TypeError", x)
    except Exception as x:
        print(type(x).__name__, repr(x.__cause__))


held(E, F)
held(E, None)
try:
    raise E from cause()
except Exception as x:
    print("named", repr(x.__cause__))
try:
    raise E from bad()
except ValueError as x:
    print("named ValueError", x)
try:
    raise E from F
except Exception as x:
    print("named", repr(x.__cause__))
maybe(None)
maybe(KeyError("m"))
