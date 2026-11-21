# sep.join(xs[lo:hi]) reads the slice's items in place. An item that is None is counted from the
# slice's first item, as in the list that CPython joins, and one outside the slice is not read.
def joined(sep: str, xs: list[str | None], lo: int, hi: int) -> None:
    try:
        print(repr(sep.join(xs[lo:hi])))
    except TypeError as e:
        print("TypeError:", e)


items: list[str | None] = ["a", "é", None, "", "🐍", None, "z"]
for lo, hi in [(0, 2), (0, 3), (1, 3), (2, 3), (3, 5), (3, 6), (4, 7), (6, 7), (-1, 7), (-2, 7), (-4, -2), (5, 5), (9, 2), (-100, 1), (3, 100)]:
    joined(", ", items, lo, hi)
    joined("", items, lo, hi)
    joined("☆", items, lo, hi)


def parts(xs: list[str], lo: int, hi: int) -> str:
    return "/".join(xs[lo:hi]) + "|" + "".join(xs[lo:]) + "|" + "<>".join(xs[:hi])


words = ["w" + str(i) for i in range(12)]
for lo, hi in [(0, 12), (0, 0), (11, 12), (3, 4), (-3, -1), (-50, 50), (7, 3)]:
    print(parts(words, lo, hi))
