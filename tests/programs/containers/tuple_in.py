class P:
    def __init__(self, x: int):
        self.x = x

    def __eq__(self, other: "P") -> bool:
        print("eq", self.x, other.x)
        return self.x == other.x


k = P(1)
print(k in (k, P(2)))
print(k in (P(3), P(4)))
print(k in (P(5), P(1), P(7)))
print(3 in (1, "a", 3.0), "a" in (1, "a"))
