class A:
    def __init__(self, x: int):
        self.x = x

    def __lt__(self, other: "A") -> bool:
        return self.x < other.x


print([A(1)] <= [A(2)])
