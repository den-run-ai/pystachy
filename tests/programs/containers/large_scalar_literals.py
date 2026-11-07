import math


def integers() -> list[int]:
    return [-9223372036854775808, 9223372036854775807, 0, -1, 4, 5, 6, 7,
            8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
            24, 25, 26, 27, 28, 29, 30, 31]


def floats() -> list[float]:
    return [-0.0, 0.0, 1e309, -1e309, 5e-324, -5e-324, 1.25, -1.25,
            8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0,
            16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0,
            24.0, 25.0, 26.0, 27.0, 28.0, 29.0, 30.0, 31.0]


def flags() -> list[bool]:
    return [True, False, True, False, True, False, True, False,
            True, True, False, False, True, True, False, False,
            False, False, True, True, False, False, True, True,
            False, True, False, True, False, True, False, True]


a = integers()
b = integers()
alias = a
print(a == b, a is b, a is alias)
alias[0] = 42
a.append(99)
print(b[0], b[1], len(a), len(b), a[0], a[-1])
copied = b.copy()
b.clear()
b.append(88)
print(len(copied), copied[0], copied[-1], b)
copied[1:4] = [2, 3, 4]
print(copied[:8])

f = floats()
g = floats()
print(f is g, f[:8])
print([math.copysign(1.0, v) for v in f[:6]])
f[0] = 4.0
f.append(3.5)
print(g[:2], f[0], f[-1], len(g), len(f))

p = flags()
q = flags()
print(p is q, p == q, p.count(True), p.count(False))
p[0] = False
p.reverse()
print(p[:4], q[:4])
q.clear()
q.extend([True, False, True])
print(q)

# Retain multiple fresh results while allocation-every-time GC is enabled by the harness.
held: list[list[int]] = []
for i in range(20):
    values = integers()
    values[0] = i
    held.append(values)
print([v[0] for v in held], held[0] is held[1], integers()[0])
