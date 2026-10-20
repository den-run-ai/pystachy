# Lists of None filled later: the first item of another type gives the list its type,
# T | None (str, a boxed float or int, an object).
def mk(n: int):
    pts = [None] * n
    for i in range(n):
        pts[i] = str(i)
    return pts


def first(n: int) -> None:
    xs = [None] * n
    xs[0] = "a"
    print(xs)


print(mk(3))
first(3)
xs = [None, None]
xs[1] = 2.5
print(xs, xs[0] is None)
ys = 3 * [None]
ys.append(7)
ys.insert(0, 1)
print(ys, len(ys), ys.count(None))
zs = [None, None]
print(len(zs))
