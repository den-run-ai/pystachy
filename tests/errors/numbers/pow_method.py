# error: pow_method.py:11: error: ** and pow() of objects are not supported (V ** V calls V.__pow__)
# Object exponents stay rejected until reflected/subclass power dispatch is implemented.
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __pow__(self, k: "V") -> "V":
        return V(self.n ** k.n)


print((V(3) ** V(2)).n)
