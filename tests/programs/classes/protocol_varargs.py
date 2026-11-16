# *args tuples and a protocol over them: each tuple outlives its call, and iterating
# them through the protocol needs StopIteration handling no other code of the program asks for.
from typing import Iterator, Protocol


class Nums(Protocol):
    def __iter__(self) -> Iterator[int]: ...


keep: list[Nums] = []


def f(*args: int) -> None:
    keep.append(args)


def g(*args: int) -> Nums:
    return args


f(1, 2)
f(3)
held = g(4, 5)
filler = [list(range(50)) for _ in range(200)]
print([list(k) for k in keep], list(held), len(filler))
