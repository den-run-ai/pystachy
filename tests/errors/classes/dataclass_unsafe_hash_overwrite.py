# error: Cannot overwrite attribute __hash__ in class P
from dataclasses import dataclass


@dataclass(unsafe_hash=True)
class P:
    x: int

    def __hash__(self) -> int:
        return self.x
