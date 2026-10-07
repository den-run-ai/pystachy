# error: mutable default P for dataclass field 'p' is not allowed
from dataclasses import dataclass


class P:
    def __init__(self, x: int):
        self.x = x

    def __eq__(self, o: "P") -> bool:
        return self.x == o.x


@dataclass
class D:
    p: P = P(1)


print(D().p.x)
