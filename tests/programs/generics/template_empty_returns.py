# A template's function returning an empty list that nothing fills, from several returns: the
# first one finds that nothing fills it, the later ones while nothing has typed it since rely
# on that (each searched the whole function: compile time grew with returns x statements), and
# a use further on that gives it a type gives the function its return type.
def pick(x):
    xs = []
    if x == 0:
        return xs
    if x == 1:
        return xs
    if x == 2:
        return xs
    ys: list[str] = xs
    if x == 3:
        return xs
    return ys


def never(x):
    out = []
    if x == 0:
        return out
    if x == 1:
        return out
    return out


a = pick(0)
a.append("s")
print(a, pick(1), pick(3), pick(4))
b: list[float] = never(1)
print(b, never(0), sum(never(2)))
