# error: ** and pow() of objects are not supported (V ** int | None calls V.__pow__)
class V:
    def __pow__(self, exponent: int | None) -> int:
        return 7


def apply(exponent: int | None) -> int:
    return V() ** exponent


print(apply(2))
