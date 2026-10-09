# error: iter() of a dict's values() in __iter__ is not supported: its iterator raises if the dict changes size
from typing import Iterator


class C:
    def __init__(self) -> None:
        self.d: dict[str, int] | None = {"a": 1, "b": 2}

    def __iter__(self) -> Iterator[int]:
        d = self.d
        assert d is not None
        return iter(d.values())  # (CPython's iterator reads each value when it steps to it)


c = C()
for v in c:
    print(v)
