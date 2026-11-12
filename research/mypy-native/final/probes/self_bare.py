from typing import Final
class C:
    def __init__(self, x: int, names: list[str]) -> None:
        self.x: Final = x
        self.names: Final = names
        self.k: Final = 3
        self.d: Final = {"a": x}
c = C(4, ["n"])
print(c.x, c.names, c.k, c.d)
