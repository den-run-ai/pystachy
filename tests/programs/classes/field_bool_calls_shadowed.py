# A function of the program's named any is not the builtin: a field its call gives is what the
# function returns
def any(xs: list[int]) -> int:
    return len(xs) * 10


class Desc:
    def __init__(self, xs: list[int]) -> None:
        self.n = any(xs)


d = Desc([1, 2])
print(d.n, d.n + 1, type(d.n).__name__)
