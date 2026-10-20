# Context managers of the program's own classes in with statements (PEP 343): __enter__() gives
# the as target; an exception in the block goes to __exit__(type, value, traceback), which
# suppresses it by returning a true value; leaving the block otherwise (its end, break,
# continue, return) calls __exit__(None, None, None). Several items nest, an __exit__ that
# raises replaces the exception, and __exit__'s parameters may be annotated as typeshed does,
# left unannotated or taken as *args. type[BaseException] values give __name__, issubclass(),
# str() and repr(); BaseException | None values str(), repr(), isinstance() and raise.
from types import TracebackType


class Tag:
    def __init__(self, name: str, swallow: bool = False) -> None:
        self.name = name
        self.swallow = swallow

    def __enter__(self) -> str:
        print("enter", self.name)
        return self.name.upper()

    def __exit__(self, et: type[BaseException] | None, ev: BaseException | None, tb: TracebackType | None) -> bool:
        print("exit", self.name, et, repr(ev), tb is None)
        if et is not None:
            print("  ", et.__name__, issubclass(et, LookupError), issubclass(et, (KeyError, OSError)), str(et), repr(et))
        return self.swallow


class Plain:
    # unannotated: each call of __exit__ is compiled for its arguments
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        print("plain exit", et, ev)
        return et is not None and issubclass(et, ValueError)


class Star:
    def __enter__(self) -> int:
        return 7

    def __exit__(self, *excinfo) -> None:
        print("star exit", len(excinfo), excinfo[1])


class Raising:
    def __init__(self, where: str) -> None:
        self.where = where

    def __enter__(self) -> "Raising":
        if self.where == "enter":
            raise OSError("from __enter__")
        return self

    def __exit__(self, et: type[BaseException] | None, ev: BaseException | None, tb: TracebackType | None) -> None:
        print("raising exit", et)
        if self.where == "exit":
            raise KeyError("from __exit__")


class MyError(Exception):
    pass


with Tag("a") as x:
    print("body", x)
with Tag("b", True) as x:
    print("body", x)
    raise KeyError("k")
print("after b")
try:
    with Tag("c"):
        raise ValueError("v")
except ValueError as e:
    print("caught", e)
with Tag("d", True):
    raise MyError("mine")
print("after d")


def loop() -> int:
    total = 0
    for i in range(4):
        with Tag("loop" + str(i)) as t:
            if i == 0:
                continue
            if i == 2:
                break
            total += len(t)
    while True:
        with Tag("while"):
            break
    with Tag("ret"):
        return total * 10
    return -1


print(loop())
with Tag("outer") as a, Tag("inner", True) as b:
    print(a, b)
    raise OSError("os")
print("after stacked")
with Tag("o2", True):
    with Tag("i2"):
        raise IndexError(3)
print("after nested")
with Plain() as p:
    print("plain body", type(p).__name__)
with Plain():
    raise ValueError("plain swallowed")
try:
    with Plain():
        raise KeyError("plain kept")
except KeyError as e:
    print("caught", e)
with Star() as s:
    print("star", s)
with Star():
    pass
try:
    with Raising("enter"):
        print("not reached")
except OSError as e:
    print("caught", e)
try:
    with Raising("exit"):
        raise ValueError("replaced")
except KeyError as e:
    print("caught", e)
try:
    with Raising("exit"):
        print("normal end")
except KeyError as e:
    print("caught", e)
m: Tag | None = None
try:
    with m:
        print("not reached")
except TypeError as e:
    print("TypeError", e)
try:
    with Tag("unpack") as (q, r):
        print("not reached", q, r)
except ValueError as e:
    print("caught", e)


def suppressed(s: str) -> int:
    with Tag("parse", True):
        n = int(s)
        return n
    print("fell through")
    return -1


print(suppressed("5"), suppressed("x"))


def unbound(s: str) -> None:
    with Tag("unbound", True):
        n = int(s)
    try:
        print(n)
    except UnboundLocalError as e:
        print("UnboundLocalError", e)


unbound("1")
unbound("y")


def show(e: BaseException | None) -> None:
    print(e, repr(e), f"[{e}]", isinstance(e, LookupError))
    if e is not None:
        print(type(e).__name__)


def reraise(e: BaseException | None) -> None:
    raise e


last: Exception | None = None
show(last)
try:
    print(int("x"))
except ValueError as e:
    last = e
show(last)
show(KeyError("key"))
try:
    reraise(last)
except ValueError as e:
    print("reraised", e, e is last)
try:
    reraise(None)
except TypeError as e:
    print("TypeError", e)


# an unannotated __exit__ is compiled for __exit__(None, None, None) too: isinstance() of its
# None value and an exception class is False there, as in CPython
class Only:
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("exit", self.name, isinstance(exc_val, KeyError), isinstance(exc_val, (IndexError, ValueError)))
        return isinstance(exc_val, KeyError)


with Only("clean"):
    pass
with Only("key"):
    raise KeyError("swallowed by isinstance")
try:
    with Only("value"):
        raise ValueError("goes on")
except ValueError as e:
    print("caught", e)


# type(v).__name__ of an exception that may be None: NoneType for None
class Named:
    def __enter__(self) -> None:
        pass

    def __exit__(self, et: type[BaseException] | None, ev: BaseException | None, tb: TracebackType | None) -> bool:
        print("Named", type(ev).__name__, type(ev).__qualname__)
        return True


with Named():
    pass
with Named():
    raise IndexError("named")
try:
    raise ValueError("a") from KeyError("b")
except ValueError as e:
    print(type(e.__cause__).__name__)
try:
    raise ValueError("no cause")
except ValueError as e:
    print(type(e.__cause__).__name__)
