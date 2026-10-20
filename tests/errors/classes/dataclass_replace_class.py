# error: replace() should be called on dataclass instances, not Q
from dataclasses import replace


class Q:
    def __init__(self) -> None:
        self.x = 1


print(replace(Q(), x=2))
