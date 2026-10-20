# error: unary_method_arity.py:6: error: __invert__ must take 0 arguments besides self
class Mask:
    def __init__(self, n: int) -> None:
        self.n = n

    def __invert__(self, width: int) -> "Mask":
        return Mask(~self.n & ((1 << width) - 1))


print((~Mask(3)).n)
