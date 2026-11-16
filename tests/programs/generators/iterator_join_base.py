# Iterators of a class and its subclass meet as the base class, as other objects do, not as the
# Iterator[T] that distinct iterators make: the value keeps its class for isinstance() and type().
import sys


class Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> "Countdown":
        return self

    def __next__(self) -> int:
        if self.n == 0:
            raise StopIteration
        self.n -= 1
        return self.n


class Skip(Countdown):
    def __next__(self) -> int:
        self.n = max(self.n - 2, 0)
        if self.n == 0:
            raise StopIteration
        return self.n


def pick(n: int):
    if n > 0:
        return Countdown(n)
    return Skip(7)


many = len(sys.argv) > 5
it = Countdown(3) if many else Skip(7)
print(isinstance(it, Skip), type(it).__name__, list(it))
both = [Countdown(2), Skip(5)]
print([type(x).__name__ for x in both], [list(x) for x in both])
for n in [2, 0]:
    r = pick(n)
    print(isinstance(r, Skip), list(r))
