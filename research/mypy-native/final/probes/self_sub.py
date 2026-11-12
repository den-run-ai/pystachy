from typing import Final
class C:
    def __init__(self, x: int) -> None:
        self.x: Final[int] = x
        self.cache: Final[dict[str, int]] = {}
        self.opt: Final[str | None] = None
c = C(4)
c.cache["a"] = 1
print(c.x, c.cache, c.opt)
