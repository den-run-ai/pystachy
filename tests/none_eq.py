class P:
    def __init__(self, x: int):
        self.x = x

    def __eq__(self, other: "P") -> bool:
        print("eq called", self.x)
        return other is not None and self.x == other.x


p = P(1)
print(None == p, None != p, p == None)
