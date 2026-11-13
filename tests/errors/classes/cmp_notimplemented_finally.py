# error: cmp_notimplemented_finally.py:9: error: return NotImplemented inside a try statement with a finally block, or a with statement, is not supported
class W:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        try:
            if not isinstance(other, W):
                return NotImplemented
            return self.n == other.n
        finally:
            print("done")


xs = [W(1), W(1)]
print(xs[0] == xs[1], xs[0] == 3)
