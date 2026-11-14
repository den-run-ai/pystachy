# A round-robin scheduler of coroutines, as an event loop runs tasks: each task runs until its
# await reaches a @types.coroutine generator that yields what it waits for; the loop resumes it
# later. Producers and consumers interleave through a shared queue, and a task's exception is kept
# for whoever reads its result.
import types
from collections import deque


@types.coroutine
def switch(why: str):
    yield why


class Channel:
    def __init__(self) -> None:
        self.items: deque[int] = deque()
        self.closed = False

    async def put(self, v: int) -> None:
        self.items.append(v)
        await switch("put")

    async def get(self) -> int:
        while len(self.items) == 0:
            if self.closed:
                return -1
            await switch("get")
        return self.items.popleft()


async def producer(ch: Channel, name: str, n: int) -> int:
    for i in range(n):
        print(name, "puts", i)
        await ch.put(i)
    return n


async def consumer(ch: Channel, name: str) -> int:
    total = 0
    while True:
        v = await ch.get()
        if v < 0:
            break
        print(name, "got", v)
        total += v
    return total


async def failing(after: int) -> int:
    for _ in range(after):
        await switch("fail soon")
    raise ValueError("task failed")


def run_all(tasks) -> None:
    ready = list(tasks)
    rounds = 0
    while len(ready) > 0:
        t = ready.pop(0)
        try:
            why = t.send(None)
            rounds += 1
            ready.append(t)
        except StopIteration:
            print("a task finished")
        except ValueError as e:
            print("a task raised:", e)
    print("rounds", rounds)


ch = Channel()
run_all([producer(ch, "p1", 3), producer(ch, "p2", 2), failing(2)])
ch.closed = True
run_all([consumer(ch, "c1"), consumer(ch, "c2")])
