# error: bitwise_method_missing.py:14: error: unsupported operand type(s) for <<=: 'Mask' and 'int'
# neither __ilshift__ nor __lshift__: CPython's TypeError, at compile time
class Mask:
    def __init__(self, n: int) -> None:
        self.n = n

    def __rshift__(self, k: int) -> "Mask":
        return Mask(self.n >> k)


m = Mask(3)
m >>= 1
print(m.n)
m <<= 1
