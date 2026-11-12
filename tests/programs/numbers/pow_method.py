class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __pow__(self, k: "V") -> "V":
        return V(self.n ** k.n)


print((V(3) ** V(2)).n)
