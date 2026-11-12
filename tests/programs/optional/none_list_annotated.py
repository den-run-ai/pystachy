# A list annotated list[None] holds None items: its slots are null pointers, which print,
# compare, search and iterate as CPython's None items do; None in it is true where it has an
# item. Ordering two of its items raises CPython's TypeError, as sort(), sorted(), min() and
# max() of two or more do, while comparing two such lists compares their lengths. (A display
# of None items without the annotation still needs one: none_list_unfilled.py.)
xs: list[None] = [None, None]
print(xs, len(xs))
xs.append(None)
print(xs, xs[0], xs[-1] is None, None in xs, None not in xs, xs.count(None), xs.index(None))
ys = xs.copy()
print(ys == xs, ys != xs, ys[1:], xs + ys, xs * 2)
print(xs.pop(), xs)
for i, x in enumerate(xs):
    print(i, x)
print(list(reversed(xs)), str(xs), repr(xs))
zs: list[None] = []
print(zs, None in zs, bool(zs))
zs.extend(xs)
print(zs, bool(zs))
print(xs < [None, None, None], xs <= xs, xs > [None])
xs.remove(None)
print(xs)
one: list[None] = [None]
print(sorted(one), min(one))
try:
    print(sorted(xs + one))
except TypeError as e:
    print("TypeError", e)
try:
    print(max(xs + one))
except TypeError as e:
    print("TypeError", e)
try:
    ws = xs + one
    ws.sort()
    print(ws)
except TypeError as e:
    print("TypeError", e)


def nones(n: int) -> list[None]:
    out: list[None] = []
    for i in range(n):
        out.append(None)
    return out


print(nones(3), nones(0))
