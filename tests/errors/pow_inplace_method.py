# error: pow_inplace_method.py:12: error: ** and pow() of objects are not supported (V **= int calls V.__ipow__)
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __ipow__(self, k: int) -> "V":
        self.n **= k
        return self


v = V(3)
v **= 2
print(v.n)
