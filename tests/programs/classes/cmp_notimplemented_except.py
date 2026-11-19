# A method that reads its operand's attributes untested, and returns NotImplemented from the
# except clause that catches the AttributeError: of None too.
from typing import Optional


class Chain:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        try:
            return self.n == other.n
        except AttributeError:
            return NotImplemented

    def __lt__(self, other):
        try:
            return self.n < other.n
        except AttributeError:
            return NotImplemented


c = [Chain(1), Chain(2), Chain(1)]
print(c[0] == c[1], c[0] == c[2], c[0] != c[2], c[0] < c[1], c[1] < c[0])
print(c[0] == None, c[0] != None, None == c[0], None != c[0])


def less(a: Chain, b: Optional[Chain]) -> None:
    try:
        print(a < b)
    except TypeError as e:
        print("TypeError", e)


less(c[0], c[1])
less(c[0], None)
print(sorted(c)[2].n, max(c).n)
