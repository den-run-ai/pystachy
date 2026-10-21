# error: __eq__ must take 1 argument besides self
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, *others):
        return len(others) == 1


print(V(1) == V(2))
