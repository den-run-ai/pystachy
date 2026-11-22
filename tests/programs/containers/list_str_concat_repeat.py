# str and list concatenation, repetition, slice assignment and deletion
def strs() -> None:
    parts = ["", "a", "é", "日本", "x" * 40, "\x80raw", "🙂"]
    for a in parts:
        for b in parts:
            c = a + b
            print(len(c), c == b + a, c[:3], (a + b + a)[-2:], len(a + "-" + b + "/" + a + "." + b + "!" + a + b))
            print(f"{a}|{b}|{len(a)}|{a}{b}{a}{b}{a}", f"<{a}>" + f"[{b}]")
    for a in parts:
        for n in (-1, 0, 1, 2, 3, 7, 65):
            m = a * n
            print(len(m), m[:6], m[-3:], m == n * a, m.count(a) if a != "" else -1)
    b1 = b"ab" + b"" + b"\x00c"
    print(b1, b1 * 3, b"" * 5, b"z" * 4, len(b"\xff" * 300))
    try:
        print(len("ab" * (2 ** 62)))
    except OverflowError as e:
        print("OverflowError:", e)
    except MemoryError:
        print("MemoryError")


def lists() -> None:
    xs = [i for i in range(12)]
    ys = xs + [100, 200]
    none: list[int] = []
    print(ys, xs + none, none + xs == xs, none + none, [1.5] + [2.5], ["a"] + ["b", "c"])
    print(xs * 2, xs * 0, xs * -3, [0] * 5, [7] * 3, ["s"] * 3, [[1]] * 2, [1.5, 2.5] * 2)
    zs = [1, 2, 3]
    zs *= 3
    print(zs)
    zs *= 1
    zs *= 0
    print(zs)
    ws = ["p", "q"]
    ws *= 4
    print(ws, len(ws))
    a = list(range(10))
    a[2:5] = [20, 30]
    print(a)
    a[1:1] = [7, 8, 9]
    print(a)
    a[::2] = [0] * len(a[::2])
    print(a)
    a[-3:] = []
    print(a)
    a[:] = a
    a[1:3] = a
    print(a)
    a[::-2] = list(range(len(a[::-2])))
    print(a)
    try:
        a[::3] = [1]
    except ValueError as e:
        print("ValueError:", e)
    try:
        a[::0] = [1]
    except ValueError as e:
        print("ValueError:", e)
    del a[2:4]
    print(a)
    del a[::3]
    print(a)
    del a[::-2]
    print(a)
    del a[5:2]
    del a[:]
    print(a, len(a))
    a.append(1)
    b = [str(i) for i in range(9)]
    del b[1:8:3]
    b[2:2] = ["x", "y"]
    del b[-1:0:-3]
    print(b)
    n = [[i] for i in range(4)]
    n[1:3] = [[9, 9]]
    m = n * 2
    m[0].append(5)
    print(n, m, (n + n)[3] is n[0])
    big = list(range(200))
    big[10:150] = [1]
    big[5:5] = list(range(1000, 1100))
    del big[::7]
    print(len(big), sum(big), big[:8], big[-4:])


strs()
lists()
