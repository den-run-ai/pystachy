# What await takes (PEP 492): a coroutine, a @types.coroutine generator, and an object whose
# __await__ is a generator method (a Future's shape); anything else raises TypeError at the await,
# as a generator of a function that types.coroutine does not mark does.
import types


class Future:
    def __init__(self) -> None:
        self.done = False
        self.value = 0

    def set_result(self, v: int) -> None:
        self.done = True
        self.value = v

    def __await__(self):
        while not self.done:
            yield self
        return self.value


@types.coroutine
def sleep0():
    yield None


def plain():
    yield 1


async def compute(f: Future) -> int:
    v = await f
    return v + 1


async def driver_checks() -> str:
    try:
        await 5
    except TypeError as e:
        print("int:", e)
    try:
        await "text"
    except TypeError as e:
        print("str:", e)
    try:
        await plain()
    except TypeError as e:
        print("generator:", e)
    try:
        await [1, 2]
    except TypeError as e:
        print("list:", e)
    return "checked"


async def checks_then_value() -> str:
    s = await driver_checks()
    return s + "!"


fut = Future()
c = compute(fut)
y = c.send(None)
print(y is fut, y.done)
y2 = c.send(None)
print(y2 is fut)
fut.set_result(41)
try:
    c.send(None)
except StopIteration:
    print("compute finished")

d = checks_then_value()
try:
    d.send(None)
except StopIteration:
    print("checks finished")


async def ticks(n: int) -> int:
    for i in range(n):
        await sleep0()
    return n


t = ticks(3)
count = 0
try:
    while True:
        print("tick yields", t.send(None))
        count += 1
except StopIteration:
    print("ticks done after", count)
