# An unknown item placeholder does not constrain a fresh comprehension's items.
def widths(h: list[str]) -> list[int]:
    maxi = []
    if h:
        maxi = [len(x) for x in h]
    return maxi


def direct(xs):
    if not xs:
        return []
    return [x * 2 for x in xs]


def nested(rows: list[list[int]]) -> list[list[int]]:
    result = []
    if rows:
        result = [[x + 1 for x in row] for row in rows]
    return result


print(widths(["ab", "c"]), widths([]))
empty_ints: list[int] = []
print(direct([1, 2]), direct(empty_ints), direct([1.5]), direct(["a"]))
print(nested([[1, 2], [3]]), nested([]))
