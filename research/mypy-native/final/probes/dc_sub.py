from dataclasses import dataclass
from typing import Final
@dataclass
class P:
    x: Final[int]
    y: Final[int] = 2
p = P(1)
print(p, p.x, p.y)
