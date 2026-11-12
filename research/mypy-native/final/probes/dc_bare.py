from dataclasses import dataclass
from typing import Final
@dataclass
class P:
    x: int
    y: Final = 2
p = P(1)
print(p, P(1, 5))
