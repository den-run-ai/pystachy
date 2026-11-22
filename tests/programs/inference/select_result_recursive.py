# A recursive call passes the selector on: the same literal, the same instance.
def flatten(xs: list[list[int]], depth: int, nested=False):
    if depth == 0:
        if nested:
            return [xs]
        return xs
    return flatten(xs, depth - 1, nested)


def countdown(n: int, keep=False):
    if n == 0:
        if keep:
            return [n]
        return n
    if keep:
        return countdown(n - 1, True) + [n]
    return countdown(n - 1) + n


print(flatten([[1], [2]], 2), flatten([[1], [2]], 1, True))
print(countdown(3), countdown(3, True))
