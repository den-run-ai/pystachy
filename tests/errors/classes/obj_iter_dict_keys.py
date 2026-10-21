# error: iter() of a dict's keys() in __iter__ is not supported: its iterator raises if the dict changes size
from typing import Iterator


class C:
    def __init__(self) -> None:
        self.d: dict[str, int] = {"a": 1}

    def __iter__(self) -> Iterator[str]:
        return iter(self.d.keys())  # (CPython raises when the loop below adds a key)


c = C()
for k in c:
    c.d["b"] = 2
print(c.d)
