# error: unsupported call pow(V,int,int)
class V:
    def __pow__(self, exponent: int, modulus: int = 0) -> int:
        return 7


print(pow(V(), 2, 3))
