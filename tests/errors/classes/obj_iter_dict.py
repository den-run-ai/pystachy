# error: iter() of dict[str,int] in __iter__ is not supported: return iter(xs) of a list xs of the items
from collections.abc import Iterator


class Keys:
    def __init__(self) -> None:
        self.d: dict[str, int] = {"a": 1}

    def __iter__(self) -> Iterator[str]:
        return iter(self.d)  # (a dict's iterator raises if the dict changes size)


print(list(Keys()))
