# A __reversed__ and an __iter__ that yield (#490): reversed() and iteration run their generators.
from typing import Iterator


class Seq:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __reversed__(self) -> Iterator[int]:
        yield self.xs[1]
        yield self.xs[0]

    def __iter__(self) -> Iterator[int]:
        for x in self.xs:
            yield x


s = Seq()
print(list(reversed(s)), list(s))
for v in reversed(s):
    print(v)
print(sorted(reversed(s)), sum(reversed(s)))
