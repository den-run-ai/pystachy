class Bag:
    def __init__(self, n: int) -> None:
        self.n = n

    def __len__(self):
        return self.n


class Shown:
    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self):
        return f"Shown({self.x})"
