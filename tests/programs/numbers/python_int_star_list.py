# pystachy: python-int
# f(*xs) of a run-time list[int] into a function whose *args is annotated int, in a module that
# opts in to promoting ints: the list's items fill the parameters before *args and make the
# tuple *args is (a runtime-length tuple holds 64-bit ints), and arithmetic on them promotes.
def total(*args: int) -> int:
    r = 1
    for a in args:
        r *= a
    return r


def first(a: int, *rest: int) -> int:
    return a * len(rest) + sum(rest)


xs = [2 ** 40, 2 ** 40, 3]
print(total(*xs), total(*xs[:1]), total(*xs[:0]))
print(first(*xs), first(*xs[1:]))
ys: list[int] = []
try:
    print(first(*ys))
except TypeError as e:
    print("TypeError", e)
