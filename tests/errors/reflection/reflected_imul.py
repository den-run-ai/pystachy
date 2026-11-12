# error: expected int, got Seq
# Reflected dispatch works, but this augmented assignment cannot retype a stored int as Seq.
class Seq:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __rmul__(self, k: int) -> "Seq":
        return Seq(self.xs * k)


n = 2
s = Seq([1])
n *= s
print(n.xs)
