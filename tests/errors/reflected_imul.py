# error: reflected_imul.py:13: error: reflected operator methods are not supported (int *= Seq calls Seq.__rmul__)
# int has no __imul__, and int.__mul__ declines a Seq: CPython calls Seq.__rmul__(s, 2)
class Seq:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __rmul__(self, k: int) -> "Seq":
        return Seq(self.xs * k)


n = 2
s = Seq([1])
n *= s
print(n.xs)
