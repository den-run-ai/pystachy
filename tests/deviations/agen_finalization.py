# Documented deviation: a suspended async generator that the program drops without finishing it is
# never closed (Pystachy has no sys.set_asyncgen_hooks, and finalizes no generator), so its finally
# blocks do not run. CPython, with no hooks set, closes it as soon as its last reference goes: here
# where the async for that made it is left by break ("release a" before "after loop"), and at del
# ("release b" before "after del"). aclose() closes one, as in CPython.
from collections.abc import AsyncIterator


async def resource(name: str) -> AsyncIterator[int]:
    print("acquire", name)
    try:
        yield 1
        yield 2
    finally:
        print("release", name)


async def main() -> None:
    async for v in resource("a"):
        print("got", v)
        break
    print("after loop")
    g = resource("b")
    print("first", await anext(g))
    del g
    print("after del")
    h = resource("c")
    print("first", await anext(h))
    await h.aclose()
    print("after aclose")


c = main()
try:
    c.send(None)
except StopIteration:
    print("end")
