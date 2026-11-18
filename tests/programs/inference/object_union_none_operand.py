# An object beside a union of objects and numbers that holds None: CPython calls the object's
# method with None, __add__ on the left and __radd__ on the right, where it takes None; with no
# method for None, None op= x raises TypeError naming both operands' types
class M:
    def __init__(self, n: int) -> None:
        self.n = n

    def __add__(self, other: object) -> "M":
        return M(self.n + 1)

    def __radd__(self, other: object) -> "M":
        return M(self.n + 10)


def pick(f: int) -> int | M:
    if f == 0:
        return None
    if f == 1:
        return 3
    return M(5)


print((M(1) + pick(0)).n, (M(1) + pick(1)).n, (M(1) + pick(2)).n)
r = pick(0) + M(1)
print(r.n)
x = pick(0)
try:
    x += 1
except TypeError as e:
    print("TypeError", e)
