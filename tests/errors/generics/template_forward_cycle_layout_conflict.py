# error: cannot infer what a() returns: it calls itself before a use shows what the list it returns holds
# b returns a's result unchanged (return a(n)): its uses in the cycle, as list[str] and list[int],
# cannot both have the layout a's later return gives that result (#595)
def empty(n):
    out = []
    return out


def a(n):
    if n <= 0:
        return empty(n)
    r: list[str] = b(n - 1)
    r.append(str(n) * 3)
    q = b(n - 1)
    if len(q) > 0:
        print("q0", q[0])
    return r


def b(n):
    return a(n)


print(a(3))
