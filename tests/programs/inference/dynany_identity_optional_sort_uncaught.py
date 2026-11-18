# pystachy: dynamic-any
# Sorting optional numbers in a program without try or with (#1502): the sorts keep no unwind
# actions, order items by value, and a comparison with None ends the program with CPython's error.


def gen(n: int) -> list[int | None]:
    xs: list[int | None] = []
    v = 3
    for i in range(n):
        v = (v * 1103515245 + 12345) % 2147483648
        xs.append(v % 97)
    return xs


def go(n: int) -> None:
    xs = gen(n)
    ys = sorted(xs, reverse=True)
    xs.sort()
    print(xs[:6], ys[:6], len(xs))
    fs: list[float | None] = [float(x) if x is not None else None for x in xs[::7]]
    fs.sort(reverse=True)
    print(fs[:4])
    zs: list[int | None] = [5, 2, None, 1]
    zs.sort()
    print("unreachable", zs)


go(300)
