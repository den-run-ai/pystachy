from collections.abc import Sequence
def total(xs: Sequence[int]) -> int:
    return sum(xs)
print(total([1, 2]), total((3, 4)))
