# a def named like a builtin replaces it everywhere: for loops, comprehensions and arguments
def reversed(xs: list[int]) -> list[int]:
    return xs


def range(n: int) -> list[int]:
    return [n, n]


def enumerate(xs: list[str]) -> list[str]:
    return xs + xs


def zip(xs: list[str]) -> list[str]:
    return xs[:1]


for x in reversed([1, 2, 3]):
    print(x)
print([x for x in reversed([1, 2, 3])])
for x in range(3):
    print(x)
print(list(range(3)), sum(range(4)), sorted(range(5)))
for s in enumerate(["a", "b"]):
    print(s)
for s in zip(["c", "d"]):
    print(s)
print(any(enumerate(["", ""])), [s for s in zip(["e", "f"])])
