# error: three-argument object pow() requires an int or bool modulus, or literal None
class Power:
    def __pow__(self, exponent: int, modulus: int | None = None) -> int:
        return 5


def power(modulus: int | None) -> int:
    return pow(Power(), 2, modulus)


print(power(3))
