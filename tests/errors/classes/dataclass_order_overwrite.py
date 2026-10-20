# error: Cannot overwrite attribute __lt__ in class P Consider using functools.total_ordering
from dataclasses import dataclass


@dataclass(order=True)
class P:
    x: int

    def __lt__(self, other: "P") -> bool:
        return self.x < other.x
