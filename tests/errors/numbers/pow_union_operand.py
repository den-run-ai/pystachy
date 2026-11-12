# error: three-argument object pow() requires concrete native operand types
class Power:
    def __pow__(self, other, modulus: int) -> int:
        return modulus


class Other:
    pass


class Exponent:
    pass


def choose(flag: bool) -> Power | Other:
    return Power() if flag else Other()


print(pow(choose(True), Exponent(), 5))
