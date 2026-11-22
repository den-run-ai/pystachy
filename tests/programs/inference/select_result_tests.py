# The tests a literal decides: an int's truth, a negative int, not, and and or beside a test of
# another value, while and assert, and a comprehension's variable or a lambda's parameter that shadows
# the selector's name.
def sign(n: int, mode: int = 1):
    if mode < 0:
        return -n
    if not mode:
        return [n]
    return str(n)


def pick(xs: list[int], first=False, strict=True):
    for x in xs:
        if first and x > 0:
            return [x]
    if first or strict:
        return xs
    return len(xs)


def count(n: int, as_list=False):
    i = 0
    out = []
    while as_list and i < n:
        out.append(i)
        i += 1
    if as_list:
        return out
    assert not as_list
    return n


def shadow(xs: list[bool], flag=False):
    ys = [flag for flag in xs if flag]
    f = lambda flag: not flag
    if flag:
        return ys, f(flag)
    return ys


print(sign(5), sign(5, -1), sign(5, 0), sign(5, mode=2), sign(5, -0))
print(pick([0, 2, 3]), pick([0, 2], True), pick([0, 2], strict=False))
print(count(3), count(3, True))
print(shadow([True, False]), shadow([False, True], True))
