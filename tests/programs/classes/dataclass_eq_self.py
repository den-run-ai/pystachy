from dataclasses import dataclass


@dataclass
class P:
    x: float


p = P(float("nan"))
print(p == p, p != p)
