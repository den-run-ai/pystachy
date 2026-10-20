# error: cannot infer what a() returns: it calls itself before a use shows what the dict it returns holds
# The dict form of template_forward_cycle_layout_conflict: dict[str, float] and the dict[int, int]
# a use without a type takes (#595)
def emptyd(n):
    out = {}
    return out


def a(n):
    if n <= 0:
        return emptyd(n)
    r: dict[str, float] = b(n - 1)
    r["k" + str(n)] = n * 0.5
    q = b(n - 1)
    for k in q:
        print("q", k, q[k])
    return r


def b(n):
    return a(n)


print(a(3))
