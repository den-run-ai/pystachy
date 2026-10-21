# pystachy: dynamic-any
# Objects iterate through Any values as CPython iterates them (#773): their __iter__ runs, then
# the iterator's __next__ until it raises StopIteration, for every consumer of an iterable (a for
# loop, list(), sorted(), sum(), min(), max(), in where the class has no __contains__, unpacking,
# str.join(), list +=, a comprehension), and a range boxed as Any iterates too.
from typing import Any, Iterator


class CountIter:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __iter__(self) -> "CountIter":
        return self

    def __next__(self) -> int:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        print("next", self.i)
        return self.i


class Count:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> CountIter:
        return CountIter(self.n)


class Words:
    def __init__(self) -> None:
        self.items: list[str] = ["b", "c", "a"]

    def __iter__(self) -> Iterator[str]:
        return iter(self.items)


c: Any = Count(3)
for v in c:
    print("for", v)
print(list(c), sorted(c, reverse=True), sum(c))
print(min(c), max(c), 2 in c, 7 in c)
a, b, d = c
print(a, b, d)
print([v * 10 for v in c])
for v in c:
    if v == 2:
        break
    print("before break", v)
it: Any = CountIter(2)
print(list(it), list(it))
w: Any = Words()
print("-".join(w), sorted(w), "c" in w)
xs: Any = [0]
xs += w
print(xs)
r: Any = range(2, 11, 3)
print(list(r), sum(r), [v + 1 for v in r], 5 in r)
for v in r:
    print("range", v)
