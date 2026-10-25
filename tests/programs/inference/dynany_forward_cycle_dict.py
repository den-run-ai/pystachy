# pystachy: dynamic-any
# An opt-in program's dicts use CPython's hash and probe table for every key type, so a call
# cycle's forwarded dict (b: return a(n), which stores its key layout as each call returns) must
# keep that table once it holds keys: the lookups after the store missed "k1" and 9
G: dict[str, int] = {"seed": 0}
H: dict[int, int] = {0: 0}


def emptyd(n):
    out = {}
    return out


def a(n):
    global G
    if n <= 0:
        return emptyd(n)
    r: dict[str, int] = b(n - 1)
    r["k" + str(n)] = n
    G = r
    return r


def b(n):
    try:
        return a(n)
    finally:
        print("in finally", n, [k for k in ["k1", "k2", "k3", "k4"] if k in G], len(G))


def emptyi(n):
    out = {}
    return out


def c(n):
    global H
    if n <= 0:
        return emptyi(n)
    r: dict[int, int] = e(n - 1)
    r[n * 8 + 1] = n
    H = r
    return r


def e(n):
    try:
        return c(n)
    finally:
        print("int keys", n, [k for k in [9, 17, 25, 33] if k in H], len(H))


print(sorted(a(3).items()))
print(sorted(c(3).items()))
