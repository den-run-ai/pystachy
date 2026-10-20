# Lists of None filled by += (a list of str, as extend() fills them) and made by a chain of
# multiplications ([None] * 2 * 3, 2 * [None] * 2): typed by their first fill, with str | None
# items, as [None] * n is.
xs = [None]
xs += ["x"]
print(xs, xs[0] is None)


def pair() -> None:
    zs = [None, None]
    zs += ["a", "b"]
    print(zs, len(zs))


pair()
grid = [None] * 2 * 3
grid[0] = "a"
print(grid)
row = 2 * [None] * 2
row[3] = "z"
print(row, row.count(None))
