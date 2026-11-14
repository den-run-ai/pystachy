# error: the builtin 'NotImplemented' cannot be used as a value
class A:
    def __init__(self, n: int) -> None:
        self.n = n

    def __add__(self, other):
        if not isinstance(other, A):
            return NotImplemented
        return A(self.n + other.n)


xs = [A(1), A(2)]
print((xs[0] + xs[1]).n)
