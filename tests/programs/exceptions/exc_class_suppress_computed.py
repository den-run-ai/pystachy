# contextlib.suppress() of class objects that an expression gives: type(e), an item and a call,
# which CPython evaluates once, where the with statement starts
import contextlib


def pick(c: type[Exception]) -> type[Exception]:
    print("pick", c.__name__)
    return c


def run(e: BaseException, kinds: list[type[Exception]]) -> None:
    with contextlib.suppress(type(e)):
        raise KeyError("k")
    print("type(e) suppressed")
    with contextlib.suppress(kinds[0], pick(ValueError)):
        raise IndexError("i")
    print("kinds[0] suppressed")
    try:
        with contextlib.suppress(type(e)):
            raise ValueError("v")
    except ValueError as x:
        print("not suppressed:", x)


run(KeyError("x"), [LookupError])
