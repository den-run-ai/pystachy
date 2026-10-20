# error: type representation exceeds 65536 bytes
# Mutual recursion must not evade the bound on exponentially growing tuple types.
def left(x, n: int) -> int:
    if n == 0:
        return 0
    return right((x, x), n - 1)


def right(x, n: int) -> int:
    if n == 0:
        return 0
    return left((x, x), n - 1)


print(left(1, 1))
