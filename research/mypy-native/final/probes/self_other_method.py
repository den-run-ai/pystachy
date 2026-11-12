from typing import Final
class C:
    def __init__(self) -> None:
        self.setup(3)
    def setup(self, x: int) -> None:
        self.x: Final = x
print(C().x)
