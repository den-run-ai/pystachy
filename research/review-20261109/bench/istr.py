import sys


def f_str_int(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(str(i))
    return t


def f_float_3f(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(f"{i / 7:.3f}")
    return t


def f_in(xs: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        if i % 150 in xs:
            t += 1
    return t


def f_key(n: int) -> int:
    d: dict[int, int] = {1: 1}
    t = 0
    for i in range(n):
        try:
            t += d[i + 2]
        except KeyError:
            t += 1
    return t


which = sys.argv[1]
if which == "str":
    print(f_str_int(200000))
elif which == "f3":
    print(f_float_3f(100000))
elif which == "in":
    print(f_in(list(range(100)), 50000))
else:
    print(f_key(50000))
