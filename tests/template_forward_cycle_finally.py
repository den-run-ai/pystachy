# A function that returns a call cycle's dict unchanged (b: return a(n)) stores its key layout in it
# as the call returns, before its finally block runs: the layout of the type a gets, which the
# block's lookups through a global alias read (#595)
G: dict[str, int] = {"seed": 0}


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
        print("in finally", n, "k1" in G, "k2" in G, len(G))


print(sorted(a(3).items()))
