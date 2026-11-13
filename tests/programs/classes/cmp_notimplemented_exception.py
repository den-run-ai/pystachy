# An exception class's __eq__ that returns NotImplemented.
class E(Exception):
    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.n = n

    def __eq__(self, other):
        if not isinstance(other, E):
            return NotImplemented
        return self.n == other.n


xs = [E(1), E(1), E(2)]
print(xs[0] == xs[1], xs[0] == xs[2], xs[0] != xs[1], xs[0] != xs[2])
print(xs[0] == 3, xs[0] != 3, xs[0] == None, xs[0] != None)
