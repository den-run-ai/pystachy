from dataclasses import dataclass
from typing import ClassVar, Final
@dataclass
class P:
    x: int
    K: ClassVar[Final[int]] = 9
print(P(1), P.K)
