# pystachy: python-int
# Async overrides in a module that opts in to promoting ints: a base's async method annotated
# int, an override returning None, and a call through the base awaiting either, whose result
# (int | None) then promotes past 64 bits.
class R:
    async def value(self) -> int:
        return 2 ** 40

    async def total(self) -> int:
        n = await self.value()
        r = n * n * 3 if n is not None else -1
        print("total", r)
        return r


class S(R):
    async def value(self) -> None:
        return None


def finish(o: R) -> None:
    try:
        o.total().send(None)
    except StopIteration:
        print("done")


finish(R())
finish(S())
