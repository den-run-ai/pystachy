# pystachy: dynamic-any
from typing import Any


class Count:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> 'CountIter':
        print('iter', self.n)
        return CountIter(self.n)

    def __len__(self) -> int:
        print('length', self.n)
        return self.n


class CountIter:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __next__(self) -> int:
        if self.i >= self.n:
            raise StopIteration('done')
        self.i += 1
        return self.i


c: Any = Count(3)
for v in c:
    print('for', v)
print('list', list(c))
print('contains', 2 in c, 4 in c)
print('sorted', sorted(c, reverse=True))
print('sum', sum(c), sum(c, 10))
a, b, d = c
print('unpack', a, b, d)
print('any', any(c), 'all', all(c))
it: Any = iter(c)
print(next(it), next(it, -1), next(it))
try:
    next(it)
except StopIteration as e:
    print('stop', e)
print('default', next(it, 'end'))
try:
    iter(it)
except TypeError as e:
    print(e)


class Contains(Count):
    def __contains__(self, item: Any) -> bool:
        print('contains method', item)
        return True


has: Any = Contains(3)
print('priority', 7 in has)


class Yielding:
    def __iter__(self):
        yield 'a'
        yield 'b'


y: Any = Yielding()
print('yielding', list(y))
pairs: Any = [[1, 2]]
pairs += c
print('extend', pairs)
