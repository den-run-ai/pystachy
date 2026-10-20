# min(), max(), sorted() and sort() of lists of int | float items (also with None), and orderings
# of such lists: an int and a float compare exactly, as in CPython, and a NaN with nothing.
xs: list[int | float] = [3, 1.5, 2, -0.5, 2.0]
print(min(xs), max(xs), sorted(xs), sorted(xs, reverse=True))
xs.sort()
print(xs, min(x for x in xs), max(x * 2 for x in xs))
big: list[int | float] = [2**53 + 1, 2.0**53]
print(sorted(big), max(big), min(big))
nan = float("nan")
withnan: list[int | float] = [1, nan, 0]
print(sorted(withnan), max(withnan), min(withnan))
bools: list[bool | int] = [True, 2, False]
print(sorted(bools), max(bools), min(bools))
rows: list[tuple[str, int | float]] = [("b", 2), ("a", 2.5), ("a", 1)]
print(sorted(rows), max(rows))
a: list[int | float] = [1, 2.5]
b: list[int | float] = [1, 3]
print(a < b, a >= b, max([a, b]), sorted([b, a]))
opt: list[int | float | None] = [3, 2.5, 1]
print(sorted(opt), min(opt), max(opt))
opt.append(None)
try:
    print(sorted(opt))
except TypeError as e:
    print(e)
first: list[int | float | None] = [None, 2.5]
try:
    print(max(first))
except TypeError as e:
    print(e)
