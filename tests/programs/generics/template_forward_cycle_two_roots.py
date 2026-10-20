# A function that returns the results of two functions of a call cycle unchanged (c), whose use
# an annotation types: each call of c returns that type, as CPython's list of strs (#595)
def empty(n):
    out = []
    return out


def r1(n):
    if n <= 0:
        return empty(n)
    x: list[str] = r2(n - 1)
    x.append("s" + str(n))
    return x


def r2(n):
    if n <= 0:
        return empty(n)
    return c(n - 1)


def c(n):
    if n % 2 == 0:
        return r1(n)
    return r2(n)


print(r1(4))
z = c(2)
print(z, len(z[0]))
