# Awaits in an except clause, a finally block, a with block and a loop over a generator: the
# coroutine suspends there and resumes with its handled exception, its context manager and its
# loop's generator intact; closing it while suspended runs that cleanup, as CPython's does.
# Deep recursion raises RecursionError, through coroutines and through those that never suspend.
import sys
import types
from collections.abc import Iterator


@types.coroutine
def step(tag: str):
    yield tag


class Manager:
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> str:
        print("enter", self.name)
        return self.name

    def __exit__(self, t, v, tb) -> bool:
        print("exit", self.name, t is not None)
        return False


def numbers() -> Iterator[int]:
    try:
        yield 1
        yield 2
        yield 3
    finally:
        print("numbers closed")


async def in_handlers() -> str:
    try:
        raise KeyError("k")
    except KeyError as e:
        await step("in except")
        print("handling", repr(e), repr(sys.exception()))
    finally:
        await step("in finally")
        print("finally done")
    return "handlers"


async def in_with() -> str:
    with Manager("m") as name:
        await step("in with " + name)
    return "with"


async def in_loop() -> int:
    total = 0
    for n in numbers():
        await step("loop " + str(n))
        total += n
    return total


def run(c) -> None:
    try:
        while True:
            print("yielded", c.send(None))
    except StopIteration:
        print("returned")


run(in_handlers())
run(in_with())
run(in_loop())

c = in_loop()
print(c.send(None), c.send(None))
c.close()
print("closed in_loop")

w = in_with()
print(w.send(None))
w.close()
print("closed in_with")


async def depth(n: int) -> int:
    if n == 0:
        return 0
    return 1 + await depth(n - 1)


async def depth_suspending(n: int) -> int:
    if n == 0:
        await step("bottom")
        return 0
    return 1 + await depth_suspending(n - 1)


async def checked() -> None:
    print(await depth(200))
    try:
        await depth(100000)
    except RecursionError:
        print("RecursionError (never suspends)")


run(checked())
d = depth_suspending(100000)
try:
    d.send(None)
except RecursionError:
    print("RecursionError (suspends)")
s = depth_suspending(50)
print(s.send(None))
try:
    s.send(None)
except StopIteration:
    print("depth 50 returned")
