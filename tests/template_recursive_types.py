# Type-changing recursion can terminate statically, shrink types, or cycle through a finite
# set of specializations. Same-type mutual recursion still reuses active instances.
def shrink(x) -> int:
    if isinstance(x, tuple):
        return shrink(x[0])
    return x


def cycle(x, n: int) -> int:
    if n == 0:
        return 7
    if isinstance(x, int):
        return cycle((x, x), n - 1)
    if isinstance(x, tuple):
        return cycle("done", n - 1)
    return cycle(1, n - 1)


def left(x, n: int) -> int:
    if n == 0:
        return len(x)
    return right(x, n - 1)


def right(x, n: int) -> int:
    if n == 0:
        return len(x)
    return left(x, n - 1)


print(shrink(3), shrink(((5, 6), 7)))
print(cycle(1, 20), cycle((1, 1), 20), cycle("done", 20))
print(left("hello", 20), right([1, 2, 3], 21))
print(() * 9223372036854775807, (1, "a") * 2, (1,) * -1)
