# sortedcontainers' SortedList of int: the examples of its docstrings (with ints for its
# letters), then edge cases: empty lists, duplicates, 64-bit extremes, negative and
# out-of-range indices and bounds, the errors' messages, operators and comparisons
from sortedcontainers import SortedList

BIG = 9223372036854775807
SMALL = -9223372036854775807 - 1

# the docstrings' examples
sl = SortedList()
print(sl, SortedList([3, 1, 2, 5, 4]))
sl.add(3)
sl.add(1)
sl.add(2)
print(sl)
sl = SortedList()
sl.update([3, 1, 2])
print(sl)
sl = SortedList([1, 2, 3, 4, 5])
print(3 in sl, 6 in sl)
sl.discard(5)
sl.discard(0)
print(sl == SortedList([1, 2, 3, 4]))
sl.remove(4)
try:
    sl.remove(0)
except ValueError as e:
    print("ValueError:", e)
sl = SortedList([1, 2, 3, 4, 5])
del sl[2]
print(sl, sl[1], sl[-1])
sl = SortedList([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
print(list(sl.islice(2, 6)), list(sl.irange(3, 6)))
sl = SortedList([10, 11, 12, 13, 14])
print(sl.bisect_left(12), sl.bisect_right(12), sl.bisect(12))
print(SortedList([1, 2, 2, 3, 3, 3, 4, 4, 4, 4]).count(3))
sl = SortedList([1, 2, 3, 4, 5])
print(sl.pop(), sl.pop(2), sl)
print(sl.index(4))
try:
    sl.index(26)
except ValueError as e:
    print("ValueError:", e)
print(SortedList([2, 1, 20]) + [3, 1, 20])
sl = SortedList([2, 1, 20])
sl += [3, 1, 20]
print(sl, SortedList([1, 2, 3]) * 3)
sl = SortedList([1, 2, 3])
sl *= 3
print(sl)

# an empty list
e = SortedList()
print("empty:", e, len(e), bool(e), not e, 5 in e, e.bisect_left(5), e.bisect_right(5), e.count(5))
print("empty ranges:", list(e.irange(1, 10)), list(e.irange()), list(e.islice(0, 3)), list(e.islice()))
for name in ["pop", "remove", "getitem", "index", "del"]:
    try:
        if name == "pop":
            e.pop()
        elif name == "remove":
            e.remove(3)
        elif name == "getitem":
            print(e[0])
        elif name == "index":
            e.index(3)
        else:
            del e[0]
    except IndexError as exc:
        print(name, "IndexError:", exc)
    except ValueError as exc:
        print(name, "ValueError:", exc)
e.discard(42)
print("after discard:", e, e == SortedList(), e < SortedList([SMALL]))

# duplicates, negatives and the 64-bit extremes
s = SortedList([5, 1, 3, 3, -7, BIG, SMALL, 0, BIG, SMALL])
s.add(3)
s.update([10, 2, 2])
print(s, len(s))
print("count:", s.count(3), s.count(2), s.count(BIG), s.count(SMALL), s.count(99))
print("in:", 3 in s, 4 in s, BIG in s, SMALL in s, BIG - 1 in s, SMALL + 1 in s)
print("index:", s.index(3), s.index(BIG), s.index(SMALL), s.index(3, 6), s.index(3, -10, -6))
print("bisect:", s.bisect_left(3), s.bisect_right(3), s.bisect_left(4), s.bisect_right(SMALL),
      s.bisect_left(BIG), s.bisect_right(BIG))
print("getitem:", s[0], s[1], s[-1], s[-2], s[len(s) // 2], s[-len(s)])
print("irange:", list(s.irange(0, 5)), list(s.irange(0, 5, (False, False))),
      list(s.irange(3, 3, (True, False))), list(s.irange(3, 3, (False, True))))
print("irange reverse:", list(s.irange(-1, 3, reverse=True)), list(s.irange(5, 4)),
      list(s.irange(BIG, BIG)), list(s.irange(SMALL, SMALL, (True, False))))
print("irange open:", list(s.irange(None, 0)), list(s.irange(3, None)),
      list(s.irange(maximum=SMALL)), list(s.irange(BIG, None, (False, True))))
print("islice:", list(s.islice(2, 6)), list(s.islice(2, 6, reverse=True)), list(s.islice(-3)),
      list(s.islice(None, -11)))
print("islice out of range:", list(s.islice(-1000, 2)), list(s.islice(12, 5000)),
      list(s.islice(5, 2)), list(s.islice(-1, 0)))
for v in [BIG - 1, SMALL + 1, 4]:
    try:
        s.remove(v)
    except ValueError as exc:
        print("ValueError:", exc)
for start, stop in [(7, 3), (0, 3), (-2, None)]:
    try:
        s.index(3, start, stop)
    except ValueError as exc:
        print("index", start, stop, "ValueError:", exc)
for i in [14, -15, BIG, SMALL + 1]:
    try:
        print(s[i])
    except IndexError as exc:
        print("getitem", i, "IndexError:", exc)
    try:
        s.pop(i)
    except IndexError as exc:
        print("pop", i, "IndexError:", exc)
    try:
        del s[i]
    except IndexError as exc:
        print("del", i, "IndexError:", exc)
print("pop:", s.pop(), s.pop(0), s.pop(2), s.pop(-2), s)
s.remove(3)
s.discard(10)
s.discard(11)
del s[0]
del s[-1]
print("after removals:", s, len(s))

# copies, operators and the methods that raise NotImplementedError
c = s.copy()
c.add(100)
print("copy:", c, s, s.__copy__() == s, c == s, c is s)
print("operators:", s + [7, -3], s * 0, s * -3, s * 2, s.__radd__([9]), s.__rmul__(2))
t = s.copy()
t += [4]
t *= 1
print("in place:", t, t == s, str(t), [t])
for name in ["setitem", "append", "extend", "insert", "reverse"]:
    try:
        if name == "setitem":
            t[0] = 1
        elif name == "append":
            t.append(1)
        elif name == "extend":
            t.extend([1])
        elif name == "insert":
            t.insert(0, 1)
        else:
            t.reverse()
    except NotImplementedError as exc:
        print(name, "NotImplementedError:", exc)

# comparisons: item by item, then by length, as for lists; and == in containers
a = SortedList([3, 1, 2])
b = a.copy()
d = SortedList([1, 2])
f = SortedList([1, 2, 4])
print("==:", a == b, a != b, a == a, a == f, a != f, a == d, SortedList() == e)
print("<:", a < f, a <= f, a > f, a >= f, f > a, d < a, a < d, a <= b, a >= b, e < d)
print("in lists:", b in [a], b in [d, f], [a, f].count(b), [f, a].index(b), [d, a] == [d, b])
print("sorted:", sorted([f, a, d, e]), min([f, a, d]), max([d, a, f]))
opt: list[SortedList | None] = [None, a]
print("with None:", opt.index(b), b in opt, opt.count(b), None in opt, a == None, a != None)
print("in tuples and dicts:", (a, 1) == (b, 1), (a, 1) != (f, 1), (a,) < (f,), (f, 0) <= (a, 9),
      [a] < [f], {"k": a} == {"k": b}, {"k": a} == {"k": f}, b in (d, a))
ys: list[SortedList | None] = [None, b, None]
ys.remove(None)
ys.remove(a)
print("optional lists:", opt == [None, b], opt == [b, None], ys, opt != ys)

# keyword arguments, by the names of upstream's methods and of the aliases written as defs
k = SortedList(iterable=[4, 1, 3, 1, 5, 9, 2, 6])
k.add(value=7)
k.update(iterable=[0, 8])
k._update(iterable=[10])
print("keywords:", k.count(value=1), k.bisect(value=3), k._bisect_right(value=3),
      k.index(value=6, start=1, stop=-1), list(k.irange(minimum=2, maximum=6,
      inclusive=(False, True), reverse=True)), list(k.islice(start=1, stop=-2, reverse=True)),
      k.pop(index=0), k._getitem(index=-1), k.__radd__(other=[1]), k.__rmul__(num=0))
print("iterated:", list(a), [x * 2 for x in s], sum(s), sorted(s, reverse=True), max(s))
