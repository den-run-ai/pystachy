# An int | IntEnum field (which may be None, as an object may) with a member as the other
# operand: each operator selects the member's operation, and None's case raises CPython's
# TypeError, as int's methods decline None, rather than compiling the member's method for None.
from enum import IntEnum


class Color(IntEnum):
    RED = 1
    GREEN = 2


class Box:
    def __init__(self, n: int | Color) -> None:
        self.n = n

    def ops(self, k: Color) -> None:
        print(self.n + k, k + self.n, self.n - k, k - self.n, self.n * k, k * self.n)
        print(self.n // k, k // self.n, self.n % k, k % self.n, self.n / k, k / self.n)
        print(self.n & k, k & self.n, self.n | k, k | self.n, self.n ^ k, k ^ self.n)
        print(self.n << k, k << self.n, self.n >> k, k >> self.n)


Box(Color.RED).ops(Color.GREEN)
Box(5).ops(Color.GREEN)
