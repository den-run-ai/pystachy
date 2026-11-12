# A generic Task deriving from a generic Future, which derives from an ordinary base, as asyncio's
# classes do: Task(coro) binds T from the Coroutine[None, None, T] it runs (None for one that
# returns None), awaiting a Future[T] gives its T, and a list of the base holds futures and tasks
# of several specializations, whose done() and the overridden describe() run through the base.
from typing import Callable, Coroutine, Generic, TypeVar

T = TypeVar("T")
ready: list[Callable[[], None]] = []
blocking: list["FutureBase"] = []


class FutureBase:
    def __init__(self) -> None:
        self.state = "PENDING"
        self.callbacks: list[Callable[[], None]] = []

    def done(self) -> bool:
        return self.state != "PENDING"

    def finish(self) -> None:
        self.state = "FINISHED"
        for cb in self.callbacks:
            ready.append(cb)
        self.callbacks.clear()

    def describe(self) -> str:
        return "future " + self.state


class Future(FutureBase, Generic[T]):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[T] = []

    def set_result(self, value: T) -> None:
        self.results.append(value)
        self.finish()

    def result(self) -> T:
        return self.results[0]

    def __await__(self):
        if not self.done():
            blocking.append(self)
            yield None
        return self.result()


class Task(Future[T]):
    def __init__(self, coro: Coroutine[None, None, T]) -> None:
        super().__init__()
        self.coro: Coroutine[None, None, None] = self.wrap(coro)
        ready.append(self.step)

    async def wrap(self, coro: Coroutine[None, None, T]) -> None:
        self.set_result(await coro)

    def step(self) -> None:
        try:
            self.coro.send(None)
        except StopIteration:
            return
        if len(blocking) > 0:
            blocking.pop().callbacks.append(self.step)
        else:
            ready.append(self.step)

    def describe(self) -> str:
        return "task " + self.state


def run() -> None:
    while len(ready) > 0:
        ready.pop(0)()


async def child(n: int, f: Future[int]) -> int:
    v = await f
    return v + n


async def shout(s: str) -> str:
    return s.upper()


async def quiet() -> None:
    print("quiet ran")


f: Future[int] = Future()
everything: list[FutureBase] = [f]
t1 = Task(child(1, f))
t2 = Task(shout("hi"))
t3 = Task(quiet())
everything.append(t1)
everything.append(t2)
everything.append(t3)
print([x.describe() for x in everything])
ready.append(lambda: f.set_result(41))
run()
print(t1.result(), t2.result(), t3.result(), [x.done() for x in everything])
print([x.describe() for x in everything])
