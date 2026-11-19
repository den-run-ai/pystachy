"""Write one program per loop pattern into k/: each reads its size from argv, runs the kernel
reps times and prints a checksum, so LLVM sees nothing constant."""
import os

HEAD = '''import sys
import math


def fill(n: int, seed: int) -> list[float]:
    out = [0.0] * n
    x = seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        out[i] = (x % 1000) / 250.0 + 0.5
    return out


def ifill(n: int, seed: int) -> list[int]:
    out = [0] * n
    x = seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        out[i] = x % 1000
    return out

'''

K = {}
K["saxpy"] = ('''
def kernel(a: float, x: list[float], y: list[float]) -> None:
    for i in range(len(x)):
        y[i] = a * x[i] + y[i]
''', '''    x = fill(n, 1)
    y = fill(n, 2)
    for r in range(reps):
        kernel(0.5, x, y)
    print(sum(y))''')
K["dot"] = ('''
def kernel(x: list[float], y: list[float]) -> float:
    s = 0.0
    for i in range(len(x)):
        s += x[i] * y[i]
    return s
''', '''    x = fill(n, 1)
    y = fill(n, 2)
    t = 0.0
    for r in range(reps):
        t += kernel(x, y)
    print(t)''')
K["isum"] = ('''
def kernel(x: list[int]) -> int:
    s = 0
    for i in range(len(x)):
        s += x[i]
    return s
''', '''    x = ifill(n, 1)
    t = 0
    for r in range(reps):
        t += kernel(x)
    print(t)''')
K["matmul"] = ('''
def kernel(a: list[float], b: list[float], c: list[float], m: int) -> None:
    for i in range(m):
        for j in range(m):
            s = 0.0
            for k in range(m):
                s += a[i * m + k] * b[k * m + j]
            c[i * m + j] = s
''', '''    m = int(math.sqrt(n))
    a = fill(m * m, 1)
    b = fill(m * m, 2)
    c = [0.0] * (m * m)
    for r in range(reps):
        kernel(a, b, c, m)
    print(sum(c))''')
K["tri"] = ('''
def kernel(x: list[float], m: int) -> float:
    t = 0.0
    for i in range(m):
        for j in range(i + 1, m):
            t += x[i] * x[j]
    return t
''', '''    m = int(math.sqrt(n))
    x = fill(m, 1)
    t = 0.0
    for r in range(reps):
        t += kernel(x, m)
    print(t)''')
K["rev"] = ('''
def kernel(x: list[float], y: list[float]) -> None:
    for i in range(len(x) - 1, -1, -1):
        y[i] = x[i] * 2.0 + y[i]
''', '''    x = fill(n, 1)
    y = fill(n, 2)
    for r in range(reps):
        kernel(x, y)
    print(sum(y))''')
K["stencil"] = ('''
def kernel(a: list[float], b: list[float]) -> None:
    for i in range(1, len(a) - 1):
        b[i] = (a[i - 1] + a[i] + a[i + 1]) * 0.25
''', '''    a = fill(n, 1)
    b = [0.0] * n
    for r in range(reps):
        kernel(a, b)
        kernel(b, a)
    print(sum(a))''')
K["divide"] = ('''
def kernel(a: list[float], b: list[float], c: list[float]) -> None:
    for i in range(len(a)):
        c[i] = a[i] / b[i]
''', '''    a = fill(n, 1)
    b = fill(n, 2)
    c = [0.0] * n
    for r in range(reps):
        kernel(a, b, c)
    print(sum(c))''')
K["sqrt"] = ('''
def kernel(a: list[float], c: list[float]) -> None:
    for i in range(len(a)):
        c[i] = math.sqrt(a[i])
''', '''    a = fill(n, 1)
    c = [0.0] * n
    for r in range(reps):
        kernel(a, c)
    print(sum(c))''')
K["foreach"] = ('''
def kernel(xs: list[float]) -> float:
    s = 0.0
    for x in xs:
        s += x
    return s
''', '''    x = fill(n, 1)
    t = 0.0
    for r in range(reps):
        t += kernel(x)
    print(t)''')
K["scale"] = ('''
def kernel(xs: list[float], ys: list[float]) -> None:
    for i in range(len(xs)):
        ys[i] = xs[i] * 3.0
''', '''    x = fill(n, 1)
    y = [0.0] * n
    for r in range(reps):
        kernel(x, y)
    print(sum(y))''')
K["iscale"] = ('''
def kernel(xs: list[int], ys: list[int]) -> None:
    for i in range(len(xs)):
        ys[i] = xs[i] * 3 + 1
''', '''    x = ifill(n, 1)
    y = [0] * n
    for r in range(reps):
        kernel(x, y)
    print(sum(y))''')
K["comp"] = ('''
def kernel(xs: list[float]) -> list[float]:
    return [x * 2.0 for x in xs]
''', '''    x = fill(n, 1)
    t = 0.0
    for r in range(reps):
        t += kernel(x)[r % n]
    print(t)''')
K["callrng"] = ('''
def bump(state: list[int], i: int) -> int:
    state[i] = (state[i] * 5 + 1) % 65536
    return state[i]


def kernel(xs: list[float], ys: list[float], state: list[int]) -> float:
    t = 0.0
    for i in range(len(xs)):
        t += xs[i] * ys[i] + bump(state, i % 3)
    return t
''', '''    x = fill(n, 1)
    y = fill(n, 2)
    st = [1, 2, 3]
    t = 0.0
    for r in range(reps):
        t += kernel(x, y, st)
    print(t)''')
K["outer"] = ('''
def kernel(h: list[int], w: list[float], out: list[float], m: int) -> None:
    for i in range(len(h)):
        acc = w[i]
        for _ in range(m):
            acc = acc * 0.5 + 1.0
        out[i] = acc + h[i]
''', '''    h = ifill(n, 1)
    w = fill(n, 2)
    out = [0.0] * n
    for r in range(reps):
        kernel(h, w, out, 3)
    print(sum(out))''')
K["knn"] = ('''
def kernel(data: list[float], m: int, dim: int, best: list[float]) -> None:
    for i in range(m):
        bi = i * dim
        b = 1e300
        for j in range(m):
            bj = j * dim
            s = 0.0
            for d in range(dim):
                diff = data[bi + d] - data[bj + d]
                s += diff * diff
            if s < b and j != i:
                b = s
        best[i] = b
''', '''    dim = 16
    m = int(math.sqrt(n * 4)) // 4
    data = fill(m * dim, 1)
    best = [0.0] * m
    for r in range(reps):
        kernel(data, m, dim, best)
    print(sum(best))''')
K["cmpcount"] = ('''
def kernel(xs: list[float], lim: float) -> int:
    c = 0
    for i in range(len(xs)):
        if xs[i] > lim:
            c += 1
    return c
''', '''    x = fill(n, 1)
    t = 0
    for r in range(reps):
        t += kernel(x, 2.0)
    print(t)''')
K["while"] = ('''
def kernel(xs: list[float], ys: list[float]) -> None:
    i = 0
    n = len(xs)
    while i < n:
        ys[i] = xs[i] + 1.0
        i += 1
''', '''    x = fill(n, 1)
    y = [0.0] * n
    for r in range(reps):
        kernel(x, y)
    print(sum(y))''')

for name, (body, run) in K.items():
    src = HEAD + body + '''

def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
''' + run + '''


main()
'''
    with open(os.path.join("k", name + ".py"), "w") as f:
        f.write(src)
print(len(K), "kernels")
