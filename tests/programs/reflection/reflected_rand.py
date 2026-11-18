# int & object calls the object's __rand__: an int has no method for it.
class Bits:
    def __init__(self, n: int) -> None:
        self.n = n

    def __rand__(self, o: int) -> int:
        return o & self.n


print(3 & Bits(6))
