# error: expected int, got str
# A different, concrete parameter annotation is still checked.
from typing import Any


class Holder:
    def __init__(self, value: Any, count: int) -> None:
        self.value = value
        self.count = count


print(Holder("value", "wrong").count)
