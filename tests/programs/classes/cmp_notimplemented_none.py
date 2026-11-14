# None beside an object whose methods return NotImplemented: on either side, and in optional
# values.
from typing import Optional


class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, V):
            return NotImplemented
        return self.n == other.n

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, V):
            return NotImplemented
        return self.n < other.n

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, V):
            return NotImplemented
        return self.n >= other.n


def show(x: Optional[V], y: Optional[V]) -> None:
    print(x == y, x != y, y == x)
    for op in ["<", ">", ">=", "<="]:
        try:
            if op == "<":
                print(x < y)
            elif op == ">":
                print(x > y)
            elif op == ">=":
                print(x >= y)
            else:
                print(x <= y)
        except TypeError as e:
            print("TypeError", e)


vs = [V(1), V(2)]
show(vs[0], vs[1])
show(vs[0], None)
show(None, vs[0])
show(None, None)
print(vs[0] == None, None == vs[0], vs[0] != None, None != vs[0])
