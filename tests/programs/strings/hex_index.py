# hex(), oct() and bin() of an object ask its class for __index__().
class Bits:
    def __init__(self, n: int) -> None:
        self.n = n

    def __index__(self) -> int:
        return self.n


class Wide(Bits):
    def __index__(self) -> int:
        return self.n * 256


def show(b: Bits) -> None:
    print(hex(b), oct(b), bin(b))


show(Bits(255))
show(Wide(1))
show(Bits(-5))
none: Bits = Bits(1) if len("x") > 1 else None
try:
    print(hex(none))
except TypeError as e:
    print("TypeError:", e)
