# An __await__ that is a @types.coroutine generator returns a coroutine, which await rejects
# (PEP 492): TypeError, before the generator runs
import types


class A:
    @types.coroutine
    def __await__(self):
        print("not reached")
        yield 1


async def f():
    await A()


try:
    f().send(None)
except TypeError as e:
    print("TypeError", e)
