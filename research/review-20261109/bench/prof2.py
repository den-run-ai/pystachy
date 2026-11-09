import sys


def b_sort_ints(n: int) -> int:
    xs = [(i * 7919 + 13) % 1000003 for i in range(n)]
    xs.sort()
    return xs[0] + xs[n // 2] + xs[-1]


def b_sort_key(n: int) -> int:
    xs = [(i * 7919 + 13) % 1000003 for i in range(n)]
    ys = sorted(xs, key=lambda v: (v % 1000, -v))
    return ys[0] + ys[n // 2] + ys[-1]


def b_sort_key_int(n: int) -> int:
    xs = [(i * 7919 + 13) % 1000003 for i in range(n)]
    ys = sorted(xs, key=lambda v: v % 1000)
    return ys[0] + ys[n // 2] + ys[-1]


def b_sort_str(n: int) -> int:
    xs = [str((i * 7919 + 13) % 1000003) for i in range(n)]
    xs.sort()
    return len(xs[0]) + int(xs[n // 2]) + int(xs[-1])


def b_str_methods(n: int) -> int:
    lines = ["  Key%d = Value %d ; comment  " % (i, i * 3) for i in range(200)]
    t = 0
    for r in range(n // 200):
        for line in lines:
            s = line.strip()
            if s.startswith("Key") and "=" in s:
                k, _, v = s.partition("=")
                v = v.split(";")[0].strip().lower()
                t += len(k.rstrip()) + v.find("e") + len(v.replace("value", "v"))
    return t


def b_list_append_pop(n: int) -> int:
    xs: list[int] = []
    for i in range(n):
        xs.append(i)
    t = 0
    while xs:
        t += xs.pop()
    return t


def b_set_build(n: int) -> int:
    a = set(range(0, n, 2))
    return len(a)


def b_dict_tuple(n: int) -> int:
    d: dict[tuple[int, int], int] = {}
    for i in range(n):
        k = (i % 300, i % 7)
        d[k] = d.get(k, 0) + i
    return len(d) + d[(5, 5)]


def b_split_join(n: int) -> int:
    t = 0
    line = "alpha,beta,gamma,delta,epsilon,zeta,eta,theta"
    for i in range(n):
        parts = line.split(",")
        t += len("-".join(parts)) + len(parts)
    return t


which = sys.argv[1]
n = int(sys.argv[2])
if which == "sort_ints":
    print(b_sort_ints(n))
elif which == "sort_key":
    print(b_sort_key(n))
elif which == "sort_key_int":
    print(b_sort_key_int(n))
elif which == "sort_str":
    print(b_sort_str(n))
elif which == "str_methods":
    print(b_str_methods(n))
elif which == "append_pop":
    print(b_list_append_pop(n))
elif which == "set_build":
    print(b_set_build(n))
elif which == "dict_tuple":
    print(b_dict_tuple(n))
else:
    print(b_split_join(n))
