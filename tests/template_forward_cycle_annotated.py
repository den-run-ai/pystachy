# A call cycle through a function that returns a(n) unchanged, whose use an annotation types: b
# returns what a returns, list[str], also where it is called after the cycle (#595)
def empty(n):
    out = []
    return out


def a(n):
    if n <= 0:
        return empty(n)
    if n == 1:
        return b(n - 1)
    r: list[str] = b(n - 1)
    r.append("x" * n)
    return r


def b(n):
    return a(n)


print(a(3))
q = b(3)
q.append("end")
print(q, len(q[0]), b(0), b(1))
