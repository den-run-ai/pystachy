# error: bitwise_method_arity.py:6: error: __xor__ must take 1 argument besides self
class Mask:
    def __init__(self, n: int) -> None:
        self.n = n

    def __xor__(self, o: "Mask", width: int) -> "Mask":
        return Mask((self.n ^ o.n) & ((1 << width) - 1))


print((Mask(3) ^ Mask(5)).n)
