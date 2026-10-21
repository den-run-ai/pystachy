# error: eq must be true if order is true
from dataclasses import dataclass


@dataclass(order=True, eq=False)
class P:
    x: int
