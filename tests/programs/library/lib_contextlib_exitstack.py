# contextlib.ExitStack (lib/contextlib.py): managers of different classes entered in one stack,
# callbacks with arguments, push() of managers, callable objects, functions and None,
# pop_all() and close(), and what leaves the stack: nothing, the body's exception, or the
# exception of an exit, in CPython's order.
import io
from contextlib import ExitStack, closing, contextmanager, suppress
from types import TracebackType


class Res:
    def __init__(self, name: str, swallow: bool = False, boom: bool = False) -> None:
        self.name = name
        self.swallow = swallow
        self.boom = boom

    def __enter__(self) -> "Res":
        print("enter", self.name)
        return self

    def __exit__(self, t: type[BaseException] | None, v: BaseException | None, tb: TracebackType | None) -> bool:
        print("exit", self.name, type(v).__name__ if v is not None else None, t is None)
        if self.boom:
            raise KeyError(self.name)
        return self.swallow


class Counter:
    def __init__(self) -> None:
        self.n = 0

    def __enter__(self) -> int:
        self.n += 1
        return self.n

    def __exit__(self, *exc_info) -> None:
        self.n -= 1


class OnlyCall:
    def __call__(self, t: type[BaseException] | None, v: BaseException | None, tb: TracebackType | None) -> bool:
        print("called", v is None)
        return False


class Closer:
    def close(self) -> None:
        print("closed")


def note(msg: str, n: int = 0) -> None:
    print("callback", msg, n)


def fn(t: type[BaseException] | None, v: BaseException | None, tb: TracebackType | None) -> None:
    print("fn", v is None)


def swallow(*exc_details) -> bool:
    print("swallow", len(exc_details))
    return True


@contextmanager
def managed(tag: str):
    print("begin", tag)
    try:
        yield tag.upper()
    finally:
        print("end", tag)


def fill(stack: ExitStack, names: list[str]) -> list[Res]:
    return [stack.enter_context(Res(name)) for name in names]


# managers of several classes, callbacks and a generator's manager, left in reverse order
with ExitStack() as s:
    a = s.enter_context(Res("a"))
    print(s.callback(note, "one", n=1) is note)
    s.callback(note, "two")
    v = s.enter_context(managed("gen"))
    counter = Counter()
    n = s.enter_context(counter)
    out = s.enter_context(io.StringIO())
    out.write("text")
    s.enter_context(closing(Closer()))
    s.enter_context(suppress(ValueError))
    b = s.enter_context(Res("b"))
    print(a.name, b.name, v, n, counter.n, out.getvalue())
print(counter.n, out.closed)
print("--")
# an exit that suppresses the body's exception hides it from the exits after it
try:
    with ExitStack() as s:
        s.enter_context(Res("a"))
        s.enter_context(Res("b", swallow=True))
        s.enter_context(Res("c"))
        raise ValueError("inner")
except ValueError as e:
    print("leaked", e)
print("after suppression")
# an exit that raises replaces the exception for the exits after it
try:
    with ExitStack() as s:
        s.enter_context(Res("a"))
        s.enter_context(Res("b", boom=True))
        raise ValueError("inner")
except KeyError as e:
    print("KeyError", e)
# a callback cannot suppress, and its own exception leaves an empty body's stack
try:
    with ExitStack() as s:
        s.callback(note, "last")
        s.callback(int, "x")
        s.callback(note, "first")
except ValueError as e:
    print("ValueError", e)
print("--")
# push(): an object with __exit__, one with __call__, functions and a lambda
c = OnlyCall()
r = Res("pushed")
with ExitStack() as s:
    print(s.push(c) is c, s.push(r) is r)
    s.push(fn)
    s.push(lambda t, v, tb: print("lambda", v is None))
try:
    with ExitStack() as s:
        s.push(swallow)
        s.push(fn)
        raise RuntimeError("body")
except RuntimeError:
    print("not reached")
print("--")
# pop_all() moves the callbacks to a new stack; close() unwinds at once, and again does nothing
stack = ExitStack()
rs = fill(stack, ["x", "y"])
print([x.name for x in rs])
other = stack.pop_all()
stack.close()
print("closed the first")
other.close()
other.close()
with other:
    other.enter_context(Res("again"))
# a stack in a stack, and an exception from __enter__, which reaches no exit of its own
with ExitStack() as outer:
    inner = outer.enter_context(ExitStack())
    inner.enter_context(Res("inner"))
    outer.callback(note, "outer")
try:
    with ExitStack() as s:
        s.enter_context(Res("ok"))
        s.enter_context(managed(""[0]))
except IndexError as e:
    print("IndexError", e)
