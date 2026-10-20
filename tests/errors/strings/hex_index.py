# error: hex() of an object is not supported: Pystachy does not call __index__
class Bits:
    def __init__(self, n: int) -> None:
        self.n = n

    def __index__(self) -> int:
        return self.n


print(hex(Bits(255)))
