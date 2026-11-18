# in and count() of tuples where a union holds complex numbers: each member compared as == does
# (complex_ueq), so 1 is found as 1+0j and an int as itself, as CPython finds them
def pick(k: int) -> int | complex:
    return 1 if k == 0 else 1 + 0j


def fpick(k: int) -> float | complex:
    return 2.5 if k == 0 else 2j


for k in range(2):
    u = pick(k)
    v = fpick(k)
    print(1 in (u,), u in (1,), u in (1.0, 2), 1j in (u,), u in (1j, 2), (u, 2).count(1), v in (2.5, 2j), 2.5 in (v,))
