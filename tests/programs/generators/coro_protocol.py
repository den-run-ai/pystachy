# The coroutine protocol (PEP 492): send(), throw() and close() of a coroutine, and of the
# coroutines and @types.coroutine generators it awaits, which they reach through each await as
# through yield from (PEP 380). A finished coroutine cannot be resumed, nor awaited again, nor
# awaited while something else awaits it; a StopIteration that leaves a coroutine is a RuntimeError.
import types


@types.coroutine
def tick(name: str):
    yield name


async def inner(n: int) -> int:
    try:
        await tick("inner a")
        await tick("inner b")
    finally:
        print("inner finally", n)
    return n * 2


async def outer() -> int:
    try:
        v = await inner(5)
        print("outer got", v)
    except GeneratorExit:
        print("outer GeneratorExit")
        raise
    return v + 1


c = outer()
print(c.send(None))
c.close()
print("closed")
c.close()
try:
    c.send(None)
except RuntimeError as e:
    print("send after close:", e)

c2 = outer()
print(c2.send(None), c2.send(None))
try:
    c2.send(None)
except StopIteration:
    print("c2 finished")
try:
    c2.send(None)
except RuntimeError as e:
    print("send finished:", e)
try:
    c2.throw(ValueError("late"))
except RuntimeError as e:
    print("throw finished:", e)


async def handler() -> int:
    try:
        await tick("handler")
    except ZeroDivisionError:
        print("handled ZeroDivisionError")
        return 5
    return 0


h = handler()
h.send(None)
try:
    h.throw(ZeroDivisionError("zero"))
except StopIteration:
    print("handler returned")

h2 = handler()
h2.send(None)
try:
    h2.throw(KeyError("k"))
except KeyError as e:
    print("thrown through:", repr(e))


async def stubborn() -> None:
    try:
        await tick("stubborn")
    except GeneratorExit:
        await tick("again")


s = stubborn()
s.send(None)
try:
    s.close()
except RuntimeError as e:
    print("close:", e)


async def first() -> int:
    return 1


async def twice() -> int:
    k = first()
    a = await k
    try:
        await k
    except RuntimeError as e:
        print("await again:", e)
    return a


async def waiter(k) -> int:
    return await k


t = twice()
try:
    t.send(None)
except StopIteration:
    print("twice returned")

busy = inner(1)
busy.send(None)
w = waiter(busy)
try:
    w.send(None)
except RuntimeError as e:
    print("awaited already:", e)
busy.close()


async def stop() -> int:
    raise StopIteration


async def calls_stop() -> int:
    return await stop()


try:
    calls_stop().send(None)
except RuntimeError as e:
    print("stop:", e)


async def boom() -> int:
    await tick("boom")
    raise KeyError("x")


async def catcher() -> int:
    try:
        await boom()
    except KeyError as e:
        print("caught", repr(e))
        return 1
    return 0


k = catcher()
print(k.send(None))
try:
    k.send(None)
except StopIteration:
    print("catcher returned")
