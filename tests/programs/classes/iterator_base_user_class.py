# A base spelled Iterable that is the program's own class, also where annotations are postponed
# (from __future__ import annotations), stays that class: its __init__ runs
from __future__ import annotations


class Iterable:
    def __init__(self) -> None:
        print("base init")


class Words(Iterable):
    def __init__(self) -> None:
        super().__init__()
        self.done = False

    def __iter__(self) -> Words:
        return self

    def __next__(self) -> str:
        if self.done:
            raise StopIteration
        self.done = True
        return "w"


print(list(Words()))
