# Range loops whose item reads and assignments run unchecked after one test of the lists' lengths
# before the loop (listguard), and loops that keep their checks: every result, and every
# IndexError with the iterations before it, is CPython's
from typing import Callable


def dot(a: list[float], b: list[float]) -> float:
    t = 0.0
    for i in range(len(a)):
        t += a[i] * b[i]
    return t


def stencil(a: list[float], b: list[float]) -> None:
    for i in range(1, len(a) - 1):
        b[i] = (a[i - 1] + a[i] + a[i + 1]) / 3.0


def matmul(x: list[list[float]], y: list[list[float]], n: int) -> list[list[float]]:
    z = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi = x[i]
        zi = z[i]
        for k in range(n):
            xik = xi[k]
            yk = y[k]
            for j in range(n):
                zi[j] += xik * yk[j]
    return z


def isum(xs: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += xs[i]
    return s


def scale(xs: list[int], k: int) -> None:
    for i in range(0, len(xs), 2):
        xs[i] = xs[i] * k


def wrap(a: list[int]) -> list[int]:
    out = [0] * len(a)
    for i in range(len(a)):
        out[i] = a[i - 1] + a[(i + 1) % len(a)]  # (a[-1] where i is 0, as CPython reads it)
    return out


def partial(a: list[float], b: list[float]) -> float:
    t = 0.0
    for i in range(len(a)):
        t += a[i] * b[i]
        print("partial", i, t)
    return t


def assign_short(a: list[float], b: list[float]) -> None:
    for i in range(len(a)):
        b[i] = a[i] * 2.0


def rebind(a: list[int], b: list[int]) -> int:
    s = 0
    xs = a
    for i in range(3):
        s += xs[i]
        xs = b
    return s


def grow(a: list[int]) -> int:
    s = 0
    for i in range(4):
        s += a[i]
        a.append(i)
    return s


def maybe(flag: bool) -> float:
    if flag:
        zs = [1.0, 2.0]
    t = 0.0
    for i in range(2):
        t += zs[i]
    return t


class P:
    def __init__(self, x: int) -> None:
        self.x = x


def objs(ps: list[P], n: int) -> int:
    s = 0
    for i in range(n):
        s += ps[i].x
    return s


def early(a: list[int], b: list[int]) -> int:
    s = 0
    for i in range(len(a)):
        if a[i] < 0:
            break
        if a[i] == 0:
            continue
        s += a[i] * b[i]
    else:
        s += 1000
    return s


def moved(a: list[int]) -> int:
    s = 0
    for i in range(len(a) - 1):
        i += 1
        s += a[i]
    return s


def gen(a: list[int], n: int):
    for i in range(n):
        yield a[i]


def guarded(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        try:
            s += a[i]
        except IndexError:
            s -= 1
    return s


def total(xs: list[int]) -> None:
    xs.append(len(xs))


def calls(a: list[int]) -> int:
    s = 0
    for i in range(len(a)):
        s += a[i]
        total(a)
    return s


def down(a: list[int]) -> list[int]:
    out = [0] * len(a)
    for i in range(len(a) - 1, -1, -1):
        out[i] = a[i] * 2
    return out


def stepped(a: list[int], step: int) -> int:
    s = 0
    for i in range(0, len(a), step):
        s += a[i]
    return s


def shrink(a: list[int]) -> None:
    a.pop()


def each(a: list[int], f: Callable[[list[int]], None]) -> int:
    s = 0
    for i in range(len(a)):
        s += a[i]
        f(a)
    return s


def main() -> None:
    a = [float(i) for i in range(10)]
    b = [float(10 - i) for i in range(10)]
    print("dot", dot(a, b), dot(a, a))
    out = [0.0] * 10
    stencil(a, out)
    print("stencil", out)
    m = [[float((i * j) % 7) for j in range(5)] for i in range(5)]
    print("matmul", matmul(m, m, 5))
    try:
        matmul(m, [[1.0, 2.0]] * 5, 5)
    except IndexError as e:
        print("matmul short", e)
    xs = [i * i for i in range(8)]
    print("isum", isum(xs, 8), isum(xs, 0), isum(xs, -3))
    try:
        isum(xs, 9)
    except IndexError as e:
        print("isum long", e)
    ys = [1, 2, 3, 4, 5]
    scale(ys, 10)
    print("scale", ys)
    print("wrap", wrap([1, 2, 3, 4]))
    try:
        partial([1.0, 2.0, 3.0], [1.0, 1.0])
    except IndexError as e:
        print("partial short", e)
    short = [0.0, 0.0]
    try:
        assign_short([1.0, 2.0, 3.0], short)
    except IndexError as e:
        print("assign short", e, short)
    same = [1.0, 2.0, 3.0]
    stencil(same, same)
    print("aliased", same)
    print("rebind", rebind([1, 2, 3], [10, 20, 30]))
    print("grow", grow([5, 6]))
    print("maybe", maybe(True))
    try:
        maybe(False)
    except UnboundLocalError as e:
        print("maybe unbound", e)
    ps = [P(i) for i in range(4)]
    print("objs", objs(ps, 4))
    try:
        objs(ps, 5)
    except IndexError as e:
        print("objs long", e)
    print("early", early([1, 0, 2, 3], [5, 6, 7, 8]), early([1, -1, 2], [1, 1, 1]))
    try:
        early([1, 2, 3], [1])
    except IndexError as e:
        print("early short", e)
    print("moved", moved([1, 2, 3, 4]))
    print("gen", list(gen([4, 5, 6], 3)))
    print("guarded", guarded([1, 2, 3], 5))
    print("calls", calls([1, 2, 3]))
    print("sum", sum(a[i] * b[i] for i in range(len(a))))
    print("empty", dot([], []), isum([], 0))
    print("down", down([1, 2, 3]))
    print("stepped", stepped([1, 2, 3, 4, 5], 2))
    try:
        stepped([1, 2], 0)
    except ValueError as e:
        print("zero step", e)
    try:
        each([1, 2, 3, 4], shrink)
    except IndexError as e:
        print("callback shrinks", e)


main()
