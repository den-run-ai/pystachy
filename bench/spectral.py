# spectral norm (Benchmarks Game): nested loops, float math, function calls
import math


def a(i: int, j: int) -> float:
    return 1.0 / ((i + j) * (i + j + 1) // 2 + i + 1)


def mul_av(v: list[float], out: list[float]) -> None:
    n = len(v)
    for i in range(n):
        s = 0.0
        for j in range(n):
            s += a(i, j) * v[j]
        out[i] = s


def mul_atv(v: list[float], out: list[float]) -> None:
    n = len(v)
    for i in range(n):
        s = 0.0
        for j in range(n):
            s += a(j, i) * v[j]
        out[i] = s


def mul_atav(v: list[float], out: list[float], tmp: list[float]) -> None:
    mul_av(v, tmp)
    mul_atv(tmp, out)


n = 500
u = [1.0] * n
v = [0.0] * n
tmp = [0.0] * n
for _ in range(10):
    mul_atav(u, v, tmp)
    mul_atav(v, u, tmp)
vbv = 0.0
vv = 0.0
for i in range(n):
    vbv += u[i] * v[i]
    vv += v[i] * v[i]
print(f"{math.sqrt(vbv / vv):.9f}")
