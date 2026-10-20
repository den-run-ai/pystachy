# A function that returns a(n) unchanged in a call cycle and gets its type from a later return of
# its own: a then returns that type (#595)
def empty(n):
    out = []
    return out


def a(n):
    if n <= 0:
        return empty(n)
    r = b(n - 1)
    r.append(n)
    return r


def b(n):
    if n != 7:
        return a(n)
    return [70, 71]


print(a(3), b(7), b(2))
