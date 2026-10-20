# error: reflected_same_class.py:12: error: unsupported operand type(s) for &: 'Bits' and 'Bits'
# Bits has no __and__; CPython calls __rand__ only for a right operand of another type, so it
# raises this TypeError
class Bits:
    def __init__(self, n: int) -> None:
        self.n = n

    def __rand__(self, o: "Bits") -> int:
        return o.n & self.n


print(Bits(3) & Bits(6))
