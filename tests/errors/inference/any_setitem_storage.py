# error: expected int, got str
from typing import Any


class Fixed:
    def __init__(self) -> None:
        self.items = [1]

    def __setitem__(self, key: Any, value: Any) -> None:
        self.items[key] = value


fixed = Fixed()
fixed[0] = "x"
