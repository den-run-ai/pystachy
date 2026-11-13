# Range loops whose list indexes add a base that no iteration changes (data[bi + d]): listguard
# runs a copy without index checks where tests before the loop find every index in range, and
# the loop as compiled elsewhere. Each result must be CPython's, including negative indexes, a
# base past the end, IndexError after the same partial writes, and bases the loop changes.
def dist2(data: list[float], i: int, j: int, dim: int) -> float:
    bi = i * dim
    bj = j * dim
    s = 0.0
    for d in range(dim):
        diff = data[bi + d] - data[bj + d]
        s += diff * diff
    return s


def window(xs: list[int], b: int, n: int) -> int:
    # offsets around the base on both sides, in every operand order
    t = 0
    for k in range(1, n):
        t += xs[b + k - 1] * 3 + xs[k + b] - xs[1 + (b + k)] + xs[(k + b) + 1]
    return t


def scatter(ys: list[int], b: int, n: int) -> int:
    # item assignments through the base, and a read of another list through it
    w = [1, 2, 3, 4, 5, 6, 7, 8]
    for k in range(n):
        ys[b + k] = ys[b + k] + w[k + b] * k
    return len(ys)


def shared(a: list[float], c: list[float], b: int, n: int) -> float:
    # two lists and one base, and one list also indexed without it
    s = 0.0
    for k in range(2, n):
        s += a[b + k] * c[k + b] - a[k - 2]
    return s


def moving(xs: list[int], n: int) -> int:
    # a base the loop changes gets no copy
    b = 0
    t = 0
    for k in range(n):
        t += xs[b + k]
        b = b - 1
    return t


def show_dist2(label: str, data: list[float], i: int, j: int) -> None:
    try:
        print(label, dist2(data, i, j, 8))
    except IndexError as e:
        print(label, "IndexError", e)


def show_window(xs: list[int], b: int, n: int) -> None:
    try:
        print("window", b, n, window(xs, b, n))
    except IndexError as e:
        print("window", b, n, "IndexError", e)


def show_scatter(label: str, b: int, n: int) -> None:
    ys = [10 * k for k in range(8)]
    try:
        print(label, scatter(ys, b, n))
    except IndexError as e:
        print(label, "IndexError", e)
    print(ys)


def show_shared(a: list[float], c: list[float], b: int, n: int) -> None:
    try:
        print("shared", b, n, shared(a, c, b, n))
    except IndexError as e:
        print("shared", b, n, "IndexError", e)


data = [float((k * 37) % 23) * 0.25 for k in range(48)]
for i, j in [(0, 1), (2, 5), (5, 0), (3, 3)]:
    show_dist2("dist2", data, i, j)
show_dist2("dist2 past", data, 5, 6)
show_dist2("dist2 negative", data, -1, 2)
xs = [k * k - 7 for k in range(20)]
for b, n in [(0, 6), (3, 10), (-5, 4), (-3, 6), (17, 3), (18, 3), (2, 1), (2, 0), (-21, 3), (2**62, 3)]:
    show_window(xs, b, n)
show_scatter("scatter", 1, 6)
show_scatter("scatter past", 3, 6)
show_scatter("scatter negative", -2, 5)
fa = [0.5 * k for k in range(16)]
fc = [1.0 + k for k in range(12)]
for b, n in [(0, 10), (4, 9), (6, 10), (-4, 8)]:
    show_shared(fa, fc, b, n)
print("moving", moving(xs, 6))
