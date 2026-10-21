# error: __eq__ must return bool, and V.__eq__() returns int
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        return self.n - other.n


print(V(1) == V(1))
