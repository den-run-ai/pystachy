# next(it, default) catches the StopIteration of a class that defines __next__ and no __iter__,
# called as next, builtins.next, an alias imported from builtins or a variable holding next.
import builtins as b
from builtins import next as step


class Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    def __next__(self) -> int:
        if self.n == 0:
            raise StopIteration
        self.n -= 1
        return self.n


c = Countdown(2)
print(next(c, -1), b.next(c, -2), step(c, -3))
take = next
print(take(Countdown(0), -4), take(Countdown(1), -5))


def drain(it: Countdown) -> list[int]:
    out: list[int] = []
    while (x := next(it, None)) is not None:
        out.append(x)
    return out


print(drain(Countdown(3)))
