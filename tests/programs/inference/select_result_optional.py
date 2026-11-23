# is None and is not None of a parameter whose default is None: annotated optional, where the
# instance for a given int holds only that int (index() takes it unnarrowed), and unannotated.
def find(xs: list[int], key: int | None = None):
    if key is None:
        return xs
    return xs.index(key)


def label(n, prefix=None):
    if prefix is not None:
        return [prefix, str(n)]
    return n


def tag(n: int, prefix: str | None = None):
    if prefix is None:
        return n
    return prefix + str(n)


print(find([4, 5]), find([4, 5], 5), find([4, 5], key=4), find([4, 5], None))
print(label(1), label(2, "x"), label(3, prefix="y"))
print(tag(1), tag(2, "t"), tag(3, None), tag(4, prefix="u"))
