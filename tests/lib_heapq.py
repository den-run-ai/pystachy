# CPython's own Lib/heapq.py (lib/heapq.py, unmodified), compiled for each element type it is
# used with: ints, floats, strings, tuples and objects ordered by __lt__
import heapq
from heapq import heappush, heappop
from dataclasses import dataclass


@dataclass
class Task:
    prio: int
    name: str

    def __lt__(self, other: "Task") -> bool:
        return self.prio < other.prio


h: list[int] = []
for x in [5, 3, 8, 1, 9, 2, 7, 3]:
    heappush(h, x)
print(h, heappop(h), heapq.heappushpop(h, 4), heapq.heapreplace(h, 0), h)
data = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0, -1]
heapq.heapify(data)
print(data, [heappop(data) for _ in range(len(data))])
fl = [2.5, -1.0, 3.25, 0.0]
heapq.heapify(fl)
print(fl, heapq.heappushpop(fl, -5.0), heapq.heappushpop(fl, 10.0), fl)
words = ["pear", "fig", "apple", "kiwi", "banana"]
heapq.heapify(words)
print(words, [heappop(words) for _ in range(3)], words)
pairs = [(3, "c"), (1, "z"), (1, "a"), (2, "b")]
heapq.heapify(pairs)
print(heappop(pairs), heappop(pairs), pairs)
tasks: list[Task] = []
for i, n in enumerate(["write", "test", "ship", "plan"]):
    heappush(tasks, Task((i * 7) % 5, n))
print([heappop(tasks).name for _ in range(len(tasks))])
mx = [1, 9, 4, 7, 3]
heapq._heapify_max(mx)
print(mx, heapq._heappop_max(mx), heapq._heapreplace_max(mx, 2), mx)
print(len(heapq.__all__), heapq.__about__.split()[0:2])
