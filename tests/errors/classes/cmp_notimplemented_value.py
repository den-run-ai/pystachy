# error: the builtin 'NotImplemented' cannot be used as a value
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        result = NotImplemented
        if isinstance(other, V):
            return self.n == other.n
        return result


xs = [V(1), V(1)]
print(xs[0] == xs[1])
