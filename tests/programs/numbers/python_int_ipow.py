# pystachy: python-int
# An int exponent returned by a function keeps in-place dispatch, even past 64 bits.
class Power:
    def __init__(self) -> None:
        self.value = 1

    def __ipow__(self, exponent: int) -> "Power":
        print("inplace", exponent)
        self.value += exponent
        return self

    def __pow__(self, exponent: int) -> "Power":
        print("fallback", exponent)
        return Power()


class Variadic:
    def __ipow__(self, *args):
        print("variadic", args)
        return self


def exponent() -> int:
    print("exponent")
    return 2 ** 70


value = Power()
alias = value
value **= exponent()
print(value.value, value is alias)
value **= 2
print(value.value, value is alias)
variadic = Variadic()
variadic **= exponent()


class Fallback:
    def __pow__(self, exponent: int) -> "Fallback":
        print("fallback", exponent)
        return self


def missing() -> Fallback:
    return None


def small_exponent() -> int:
    print("small exponent")
    return 2


none = missing()
try:
    none **= small_exponent()
except TypeError as error:
    print(error)
