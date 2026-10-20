# A lib generic specialized while declaring a dataclass field must not change
# the class registry being iterated. The factory also binds its own specialization.
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Queue:
    values: deque[int] = field(default_factory=lambda: deque[int]())


a = Queue()
b = Queue()
a.values.extend([3, 4])
print(a.values, b.values)
print(a.values.popleft())
print(a)
