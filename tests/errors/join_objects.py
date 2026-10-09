# error: sequence item 0: expected str instance, P found
from typing import Iterator


class P:
    def __str__(self) -> str:
        return "p"


class B:
    def __init__(self) -> None:
        self.ps = [P()]

    def __iter__(self) -> Iterator[P]:
        return iter(self.ps)


print("".join(B()))
