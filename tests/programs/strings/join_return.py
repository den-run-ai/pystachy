# Functions without a return annotation that return values of several types: the union of
# their types.
def parse(s: str):
    if s.isdigit():
        return int(s)
    return s


def half(n: int):
    if n % 2 == 0:
        return n // 2
    return n / 2


def depth(xs: list[int], i: int):
    if i >= len(xs):
        return 0.5
    return xs[i] + depth(xs, i + 1)


print(parse("12"), parse("ab"), parse("7") == 7)
print(half(4), half(5), half(4) + half(5))
print(depth([1, 2, 3], 0))
