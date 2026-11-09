import sys


class Holder:
    def __init__(self) -> None:
        self.items: list[int] = [1, 2, 3, 4, 5, 6, 7, 8]

    def shrink(self) -> None:
        self.items = [9]


G: list[int] = [10, 20, 30, 40, 50, 60]


def rebind_global() -> None:
    global G
    G = [7]


def t1(xs: list[int], ys: list[int]) -> int:
    t = 0
    for i in range(len(xs)):
        t += xs[i]
        xs = ys
    return t


def t2(c: Holder) -> int:
    t = 0
    for i in range(len(c.items)):
        t += c.items[i]
        c.shrink()
    return t


def t3() -> int:
    t = 0
    for i in range(len(G)):
        t += G[i]
        rebind_global()
    return t


def t4(xs: list[int]) -> int:
    t = 0
    for i in range(len(xs)):
        i += 5
        t += xs[i]
    return t


def t5(xs: list[int], ys: list[int]) -> int:
    t = 0
    for i, x in enumerate(xs):
        t += ys[i] + x
    return t


def t6(xs: list[int]) -> int:
    t = 0
    alias = xs
    for i in range(len(xs)):
        t += xs[i]
        if i == 2:
            del alias[3:]
    return t


def t7(xs: list[int]) -> int:
    t = 0
    for i in range(0, len(xs), 2):
        t += xs[i + 1]
    return t


def t8(xs: list[int]) -> int:
    t = 0
    for i in range(len(xs)):
        j = i - 1
        t += xs[j] * (i + 1)
        t += xs[-i]
    return t


def t9(xss: list[list[int]]) -> int:
    t = 0
    for i in range(len(xss[0])):
        t += xss[0][i]
        if i == 1:
            xss[0] = [5]
    return t


def t10(xs: list[int], n: int) -> int:
    t = 0
    for i in range(n, len(xs)):
        t += xs[i]
    return t


def t11(xs: list[int], k: int) -> int:
    t = 0
    for i in range(len(xs) - k):
        t += xs[i + k]
    return t


def t12(xs: list[int]) -> int:
    t = 0
    i = 0
    while i < len(xs):
        t += xs[i]
        if t > 5:
            xs.pop()
        i += 1
    return t


def t13(xs: list[int]) -> int:
    t = 0
    n = len(xs)
    xs.pop()
    xs.pop()
    for i in range(n):
        t += xs[i]
    return t


def t14(xs: list[int], f) -> int:
    t = 0
    for i in range(len(xs)):
        t += xs[i]
        f(i)
    return t


def t15(xs: list[str]) -> str:
    out = ""
    for i in range(len(xs)):
        out += xs[i]
        if xs[i] == "c":
            xs.remove("d")
    return out


def run(label: str, f) -> None:
    try:
        print(label, f())
    except Exception as e:
        print(label, type(e).__name__, e)


def main(extra: int) -> None:
    run("t1", lambda: t1([1, 2, 3, 4, 5], [100 + extra]))
    run("t2", lambda: t2(Holder()))
    run("t3", lambda: t3())
    run("t4", lambda: t4([1, 2, 3, 4, 5, 6, 7, 8, 9, 10 + extra]))
    run("t5", lambda: t5([1, 2, 3, 4 + extra], [1, 2]))
    run("t6", lambda: t6([1, 2, 3, 4, 5, 6 + extra]))
    run("t7", lambda: t7([1, 2, 3, 4, 5 + extra]))
    run("t8", lambda: t8([1, 2, 3, 4, 5 + extra]))
    run("t9", lambda: t9([[1, 2, 3, 4 + extra], [0]]))
    run("t10", lambda: t10([1, 2, 3, 4 + extra], -2))
    run("t10b", lambda: t10([1, 2, 3, 4 + extra], -9))
    run("t11", lambda: t11([1, 2, 3, 4 + extra], -1))
    run("t11b", lambda: t11([1, 2, 3, 4 + extra], -3))
    run("t12", lambda: t12([1, 2, 3, 4, 5, 6, 7, 8 + extra]))
    run("t13", lambda: t13([1, 2, 3, 4, 5, 6, 7, 8 + extra]))
    ys = [1, 2, 3, 4, 5, 6 + extra]

    def chop(i: int) -> None:
        if i == 1:
            ys.clear()

    run("t14", lambda: t14(ys, chop))
    run("t15", lambda: t15(["a", "b", "c", "d", "e"]))


main(len(sys.argv) - 1)
