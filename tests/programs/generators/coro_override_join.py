# Async overrides whose coroutines differ: a call through the base awaits any of them, so they
# make coroutines of one type, what they yield and what they return joined, as their results
# join for ordinary overrides. A base that raises NotImplementedError, an override returning an
# int and one returning None give int | None; a base that never suspends and an override that
# yields ints give coroutines that yield int | None (pyperformance's async_tree has both).
import types


@types.coroutine
def suspend(n: int):
    yield n


class A:
    async def work(self):
        raise NotImplementedError("work")

    async def run(self):
        return await self.work()


class B(A):
    async def work(self):
        return 1


class C(A):
    async def work(self):
        return None


class D(A):
    async def work(self):
        await suspend(7)
        return 2


def drive(o: A) -> None:
    c = o.run()
    try:
        while True:
            print("yielded", c.send(None))
    except StopIteration:
        print("done")
    except NotImplementedError as e:
        print("NotImplementedError", e)


for o in [A(), B(), C(), D()]:
    drive(o)


class P:
    async def step(self) -> None:
        return None

    async def go(self) -> None:
        await self.step()


class Q(P):
    async def step(self) -> None:
        await suspend(3)


def drive2(o: P) -> None:
    c = o.go()
    try:
        while True:
            print("yielded", c.send(None))
    except StopIteration:
        print("done")


drive2(P())
drive2(Q())


class R:
    async def value(self) -> int:
        return 5

    async def total(self) -> int:
        n = await self.value()
        return n if n is not None else -1


class S(R):
    async def value(self) -> None:
        return None


def finish(o: R) -> None:
    try:
        o.total().send(None)
    except StopIteration:
        print("total done")


finish(R())
finish(S())
