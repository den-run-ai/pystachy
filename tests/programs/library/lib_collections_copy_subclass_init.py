# Copy invokes the subclass's constructor; an unbounded deque passes only the source.
from collections import Counter, deque

events: list[str] = []


class InitCounter(Counter[str]):
    def __init__(self, source: Counter[str]) -> None:
        super().__init__(source)
        events.append('counter')


class InitDeque(deque[int]):
    def __init__(self, source: deque[int], *args: int) -> None:
        super().__init__(source, *args)
        events.append('deque ' + str(len(args)))


c = InitCounter(Counter('abb'))
events.clear()
d = c.copy()
print(type(d).__name__, repr(d), events)
q = InitDeque(deque([1, 2]))
events.clear()
r = q.copy()
print(type(r).__name__, repr(r), events)


class NestedQueue(deque):
    pass


item = [1]
nested = NestedQueue([item], 3)
duplicate = nested.copy()
duplicate[0].append(2)
duplicate.append([3])
print(type(duplicate).__name__, nested[0], duplicate[0], duplicate[0] is nested[0], len(nested), len(duplicate))
q = InitDeque(deque([1, 2]), 3)
events.clear()
r = q.copy()
print(type(r).__name__, repr(r), events)
