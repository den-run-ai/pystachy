# error: cannot infer what a() returns: it calls itself before a use shows what the list it returns holds
# b returns a's result unchanged, and later a list of strs, which a, whose use of b's result holds
# ints, cannot return (#595)
def empty(n):
    out = []
    return out


def a(n):
    if n <= 0:
        return empty(n)
    r: list[int] = []
    for x in b(n - 1):
        r.append(len(x))
    return a(n - 1) if n > 5 else r


def b(n):
    if n != 7:
        return a(n)
    return ["s", "tt"]


print(a(3), b(7))
