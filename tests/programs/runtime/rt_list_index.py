from dataclasses import dataclass


@dataclass
class P:
    x: int


print([P(1)].index(P(2)))
