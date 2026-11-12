class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __ipow__(self, k: "V") -> "V":
        self.n **= k.n
        return self


v = V(3)
v **= V(2)
print(v.n)
