from typing import Optional


class P:
    def __init__(self, x: int):
        self.x = x

    def __lt__(self, o: "P") -> bool:
        return self.x < o.x

    def __gt__(self, o: Optional["P"]) -> bool:
        return o is None or self.x > o.x


a: Optional[P] = None
print(a < P(1))
