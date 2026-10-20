# error: unsupported decorator @lru_cache
from functools import lru_cache


class Grid:
    def __init__(self, n: int) -> None:
        self.n = n

    @lru_cache(maxsize=8)
    def cell(self, i: int) -> int:
        return i * self.n


print(Grid(3).cell(2))
