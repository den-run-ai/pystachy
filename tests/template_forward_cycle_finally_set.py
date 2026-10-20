# The set form of template_forward_cycle_finally (#595)
G: set[str] = {"seed"}


def emptys(n):
    out = set()
    return out


def a(n):
    global G
    if n <= 0:
        return emptys(n)
    r: set[str] = b(n - 1)
    r.add("k" + str(n))
    G = r
    return r


def b(n):
    try:
        return a(n)
    finally:
        print("in finally", n, "k1" in G, "k2" in G, len(G))


print(sorted(a(3)))
