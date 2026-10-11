# error: pow_method.py:11: error: ** and pow() of objects are not supported (V ** int calls V.__pow__)
# CPython calls V.__pow__(v, 2); not CPython's TypeError, which would read as if the program were wrong
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __pow__(self, k: int) -> "V":
        return V(self.n ** k)


print((V(3) ** 2).n)
