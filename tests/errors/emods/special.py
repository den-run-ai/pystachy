class Bag:
    def __init__(self, n: int) -> None:
        self.n = n

    def __len__(self):
        return self.n


class Pair:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Pair) and other.x == self.x
