from dataclasses import dataclass
from typing import Optional


@dataclass
class P:
    x: int


xs: list[Optional[P]] = [P(1), None]
xs.sort()
