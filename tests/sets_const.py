# A set display of constants is CPython's frozenset constant, which Pystachy makes once, where the
# display first runs, and keeps (in a global the collector scans): each run copies it into a new
# set, and the iterable of a for loop or a comprehension, or the right operand of in, is the
# constant itself. Each run gets a set of its own, in CPython's order
def fresh() -> set[int]:
    return {8, 16, 1, 9, 24}


def grow() -> int:
    s = {5, 6, 7}
    s.add(len(s) * 10)
    return len(s)


a = fresh()
a.add(100)
b = fresh()
print(list(a), list(b), a is b, a == b, grow(), grow(), grow())


def vowels(s: str) -> int:
    n = 0
    for c in s:
        if c in {"a", "e", "i", "o", "u"}:
            n += 1
        if c not in {"x", "y"}:  # (two items: also a frozenset constant there)
            n += 10
    return n


print(vowels("onomatopoeia"), vowels("xyz"), [vowels(w) for w in ["ab", "", "ux"]])


def total(k: int) -> int:
    t = 0
    for _ in range(k):
        for x in {9, 1, 17, 25, 2}:  # (t depends on the order)
            t = (t * 3 + x) % 1000003
    return t


print(total(1), total(4), [x * 2 for x in {33, 1, 65, 97, 2}], [x for x in {3, 11, 19} if x > 3])


def has(x):
    return x in {1, 2, 3}


print(has(2), has(5), has(True), has(-1))
junk = [[i] * 10 for i in range(20000)]  # (collections while the constants are kept)
print(len(junk), list(fresh()), total(2), vowels("queue"), has(3))


print([i in {0, 2, 4} or i in {7, 9, 11} for i in range(12)])
for x in {40, 8, 24}:
    print(x, end=" ")
print()


def bad() -> int:
    n = 0
    for _ in range(2):
        try:
            n += len({1 // 0, 2, 3})  # (it raises on each run: no constant is kept)
        except ZeroDivisionError:
            n += 100
    return n


print(bad(), bad())


def big() -> set[str]:
    # (CPython leaves "a" * 4097 to run, beyond its folding limit: a new string on each run)
    return {"a" * 4097, "b", "c"}


x1 = [s for s in big() if len(s) > 1][0]
x2 = [s for s in big() if len(s) > 1][0]
print(x1 is x2, x1 == x2, len(x1), "a" * 4097 in {"a" * 4097, "b"}, "a" * 4096 in {"a" * 4097, "b"})
