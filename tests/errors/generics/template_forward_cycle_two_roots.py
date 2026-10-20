# error: cannot infer what r1() returns: it calls itself before a use shows what the list it returns holds
# c returns the results of both r1 and r2 unchanged, and r2 returns c's: r1's use of r2's result,
# which holds r1's, cannot take the layout of r1's later return (#595)
def empty(n):
    out = []
    return out


def r1(n):
    if n <= 0:
        return empty(n)
    x = r2(n - 1)
    if len(x) > 0:
        print("x0", x[0])
    if n > 2:
        return ["s" + str(n)]
    return empty(n)


def r2(n):
    if n <= 0:
        return empty(n)
    return c(n - 1)


def c(n):
    if n % 2 == 0:
        return r1(n)
    return r2(n)


print(r1(6))
