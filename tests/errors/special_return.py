# error: __eq__ must return bool
class P:
    def __init__(self, x: int):
        self.x = x

    def __eq__(self, other: "P") -> int:
        return self.x - other.x


print(P(3) == P(1))
