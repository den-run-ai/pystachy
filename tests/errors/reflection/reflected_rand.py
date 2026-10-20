# error: reflected_rand.py:10: error: reflected operator methods are not supported (int & Bits calls Bits.__rand__)
class Bits:
    def __init__(self, n: int) -> None:
        self.n = n

    def __rand__(self, o: int) -> int:
        return o & self.n


print(3 & Bits(6))
