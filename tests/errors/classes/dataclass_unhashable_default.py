# error: mutable default <class '__main__.P'> for field p is not allowed: use default_factory
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
