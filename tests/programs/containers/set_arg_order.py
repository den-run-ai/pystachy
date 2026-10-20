# A set method that takes several iterables evaluates every argument first, in order, then takes
# the items of each in turn, as CPython's setobject.c does: a generator expression (or map(),
# filter(), zip(), ...) makes its iterator among the arguments (its outermost iterable is
# evaluated, range() checks its step, __iter__ runs) and yields its items at its turn; any other
# iterable's __iter__ runs at its turn, and None raises there. update() adds a generator's items
# as they come, difference_update() discards them so, and issuperset() and isdisjoint() stop at
# the item that decides.
from typing import Callable, Iterator


def show(tag: str, s: set[int]) -> None:
    print(tag, sorted(s))


class Items:
    def __init__(self, tag: str, xs: list[int], watch: set[int]) -> None:
        print("make", tag)
        self.tag = tag
        self.xs = xs
        self.watch = watch

    def __iter__(self) -> Iterator[int]:
        print("iter", self.tag, sorted(self.watch))
        return iter(self.xs)


def arg(tag: str, xs: list[int]) -> list[int]:
    print("arg", tag)
    return xs


def item(tag: str, x: int, s: set[int]) -> int:
    print("item", tag, x, sorted(s))
    return x


# the regression: a later generator's iterator fails while the arguments are evaluated, before
# the set takes any item
s = {1, 2}
try:
    s.update([3], (x for x in range(1, 2, 0)))
except ValueError as e:
    print("ValueError:", e)
show("after failed update", s)
try:
    s.update((x for x in [5]), [6], map(abs, range(0, 1, 0)))
except ValueError as e:
    print("ValueError:", e)
show("after failed update 2", s)
f = frozenset([1])
try:
    print(sorted(f.union([2], (x for x in range(1, 2, 0)))))
except ValueError as e:
    print("ValueError:", e)

# evaluation order: every argument's expression, then each argument's items, in turn
s = {1}
s.update(arg("a", [2]), (item("gen", x, s) for x in arg("b", [3, 4])), Items("c", [5], s), arg("d", [6]))
show("update", s)

# None raises at its turn, once the arguments before it have added their items
s = {1}
none: list[int] | None = None
try:
    s.update([2], (item("gen", x, s) for x in [3]), none, [4])
except TypeError as e:
    print("TypeError:", e)
show("after None", s)

# a generator over the set itself sees the items the arguments before it added
s = {1}
try:
    s.update([2], (x + 10 for x in s))
except RuntimeError as e:
    print("RuntimeError:", e)
show("own items", s)
s = {1, 2}
s.update([2], (x for x in s if x < 0), [3])
show("own items, none added", s)

# a dict whose iterator a generator made is changed by a later argument: its traversal fails
d = {1: "a", 2: "b"}


def grow() -> list[int]:
    d[3] = "c"
    return [7]


s = {0}
try:
    s.update((k for k in d), grow())
except RuntimeError as e:
    print("RuntimeError:", e)
show("dict grew", s)

# a later argument changes a list that an earlier generator iterates: the generator sees it
xs = [1, 2]


def clear() -> list[int]:
    xs.clear()
    return [9]


s = set()
s.update((x for x in xs), clear())
show("list cleared", s)
xs = [1, 2]
s = {0}
s.update(map(abs, xs), clear(), (y for y in range(2)))
show("list cleared 2", s)
ps = {(0, 0)}
xs = [1, 2]
ps.update(zip(xs, xs), [(5, 5)] if len(clear()) > 0 else [], enumerate(xs))
print("zip of a cleared list", sorted(ps))

# a generator that fails midway: the items it gave before stay added
s = {1}


def bad(x: int) -> int:
    if x == 3:
        raise ValueError("bad item")
    return x


try:
    s.update([2], (bad(x) for x in [10, 3, 11]))
except ValueError as e:
    print("ValueError:", e)
show("partial update", s)

# union, intersection and difference take their arguments' items in turn too
s = {1, 2, 3, 4}
print("union", sorted(s.union(arg("a", [5]), (item("u", x, s) for x in arg("b", [6])), Items("c", [7], s))))
print("intersection", sorted(s.intersection((item("i", x, s) for x in arg("a", [1, 2, 3])), Items("b", [2, 3, 9], s), arg("c", [3, 2]))))
print("difference", sorted(s.difference(Items("a", [1], s), (item("d", x, s) for x in arg("b", [2])), arg("c", [3]))))
t = {1, 2, 3, 4}
t.intersection_update(arg("a", [1, 2, 3]), (item("iu", x, t) for x in arg("b", [2, 3])), Items("c", [3], t))
show("intersection_update", t)
t = {1, 2, 3, 4, 5}
t.difference_update(arg("a", [1]), (item("du", x, t) for x in arg("b", [2, 3])), Items("c", [4], t))
show("difference_update", t)
fz = frozenset([1, 2, 3])
print("frozenset union", sorted(fz.union((x for x in [4]), Items("f", [5], set(fz)))))
print("frozenset difference", sorted(fz.difference([1], (x for x in [2]))))

# difference_update() discards a generator's items as it yields them
t = {1, 2, 3}
t.difference_update(x for x in [1, 2, 3] if len(t) > 1)
show("discarding as yielded", t)
t = {1, 2, 3}
try:
    t.difference_update(bad(x) for x in [1, 3, 2])
except ValueError as e:
    print("ValueError:", e)
show("partial difference_update", t)
t = {1, 2, 3}
t.difference_update(x for x in [2, 9])
show("difference_update gen", t)

# issuperset() and isdisjoint() stop at the item that decides
s = {1, 2, 3}
print("issuperset", s.issuperset(item("sup", x, s) for x in [1, 4, 2]))
print("issuperset all", s.issuperset(item("sup", x, s) for x in [1, 2] if x > 0))
print("isdisjoint", s.isdisjoint(item("dis", x, s) for x in [7, 2, 8]))
print("isdisjoint all", s.isdisjoint(item("dis", x, s) for x in [7, 8]))
print("frozenset issuperset", frozenset([1]).issuperset(x for x in [1, 1]))

# a set whose first update() types it takes the first argument's items at its turn too
w = set()
w.update(Items("first", [1, 2], {0}), (item("w", x, {0}) for x in arg("second", [3])))
print("typed by first", sorted(w))
v = set()
v.update((x for x in [4]), [5], Items("third", [6], {0}))
print("typed by generator", sorted(v))

# one argument: as before
s = {1}
s.update(x * 2 for x in [1, 2])
s.update(Items("one", [7], s))
s.update(map(abs, [-8]))
s.update(range(9, 10))
show("one argument", s)

# union() and difference() copy the set once the arguments are evaluated, before a generator runs
# or __iter__ runs: what those add to the set is not in the result


def grow_s(xs: list[int]) -> list[int]:
    s.add(100)
    return xs


def add_and_give(x: int) -> int:
    s.add(200)
    return x


class Adds:
    def __iter__(self) -> Iterator[int]:
        s.add(300)
        return iter([1])


s = {1, 2}
print("union first iterable", sorted(s.union(x for x in grow_s([5]))), sorted(s))
s = {1, 2}
print("union body", sorted(s.union(add_and_give(x) for x in [5])), sorted(s))
s = {1, 2}
print("union __iter__", sorted(s.union(Adds())), sorted(s))
s = {1, 2}
print("difference first iterable", sorted(s.difference(x for x in grow_s([1]))), sorted(s))
s = {1, 2}
print("difference body", sorted(s.difference(add_and_give(x) for x in [1])), sorted(s))
s = {1, 2}
print("difference __iter__", sorted(s.difference(Adds())), sorted(s))
s = {1, 2}
print("difference of two", sorted(s.difference(Adds(), (add_and_give(x) for x in [2]))), sorted(s))

# map() and filter() are generators too: their function is evaluated once, before the items


def make_fn(tag: str) -> Callable[[int], int]:
    print("function", tag)
    return abs


def loud(x: int) -> int:
    print("map item", x)
    return x


s = {1, 2, 3}
print("symmetric_difference map", sorted(s.symmetric_difference(map(make_fn("sd"), [-3, 4]))))
print("issubset map", s.issubset(map(make_fn("sub"), [-1, -2, -3])))
print("issuperset map", s.issuperset(map(loud, [1, 9, 2])))
print("isdisjoint filter", s.isdisjoint(filter(None, [0, 7, 3, 8])))
print("union map", sorted(s.union(map(make_fn("u"), [-7]))))

# a range among several arguments is made with them, not iterated: the argument after a huge one
# raises before any of its items is made
def boom() -> list[int]:
    raise ValueError("boom")


s = {1}
try:
    s.update(range(10**15), boom())
except ValueError as e:
    print("ValueError:", e)
try:
    print(sorted(s.union(range(10**15), boom())))
except ValueError as e:
    print("ValueError:", e)
try:
    s.update(range(1, 2, 0), boom())
except ValueError as e:
    print("ValueError:", e)
w = set()
try:
    w.update(range(10**15), boom())
except ValueError as e:
    print("ValueError:", e)
s.update(range(3), [9], range(5, 2, -1))
print("ranges", sorted(s))
s.difference_update(range(2), range(4, 6))
print("ranges discarded", sorted(s))
