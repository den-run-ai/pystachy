from dataclasses import dataclass
from typing import final
@final
@dataclass
class P:
    x: int
print(P(1))
