# pystachy: python-int
# The iterators that iter() makes of a list, a tuple, a dict and a set give the ints past 64 bits
# that they hold, also in tuples: next(), next() with a default, for loops, the builtins that take
# an iterator, exhaustion, the errors of a dict or a set that changes size, an object whose
# __iter__ returns iter(), and a module that does not opt in (fixed_iterators).
from typing import Iterator

from fixed_iterators import count, drain, first, keys_of, made, pairs_of

big = 2 ** 64
low = -2 ** 63
xs = [big, 1, low, -(2 ** 70)]
it = iter(xs)
print(next(it), next(it), next(it), next(it), next(it, 0), next(it, -big))
xs.append(big * 3)
print(next(it, 0), next(it, big))  # (an exhausted iterator stays so)
it = iter(xs)
print(next(it))
xs.append(2 ** 100)  # (a list's iterator sees the items appended meanwhile)
print(list(it), sum(iter(xs)), max(iter(xs)), min(iter(xs)), sorted(iter(xs)))
acc = 0
for x in iter(xs):
    acc += x * x
print(acc, [x // 3 for x in iter(xs)], list(enumerate(iter(xs[:2]))), list(zip(iter(xs), iter(xs[1:]))))

t = (big, 2, low)
ti = iter(t)
print(next(ti), list(ti), next(ti, 5), sorted(iter(t)), list(iter((big, big + 1))))

d = {big: big + 1, 3: low, low: 2 ** 70}
print(next(iter(d)), next(iter(d.keys())), next(iter(d.values())), next(iter(d.items())))
print(list(iter(d)), list(iter(d.values())), list(iter(d.items())))
for k in iter(d):
    print(k, d[k], k in d)
for k, v in iter(d.items()):
    print(k + v)
di = iter(d)
print(next(di))
d[2 ** 80] = 1
try:
    print(next(di))
except RuntimeError as e:
    print("RuntimeError:", e)
try:
    print(next(di))
except RuntimeError as e:
    print("RuntimeError again:", e)
dv = iter(d.values())
print(list(dv), next(dv, -1))

s = {big, low, 7}
print(list(iter(s)), sorted(iter(s)), max(iter(s)))
si = iter(s)
print(next(si) in s)
s.add(2 ** 90)
try:
    print(next(si))
except RuntimeError as e:
    print("RuntimeError:", e)
fs = frozenset([big, -big])
print(sorted(iter(fs)))

ps = [(big, 1), (2, low)]
pi = iter(ps)
print(next(pi), next(pi), next(pi, (0, 0)))
tk = {(big, 1): (2, big), (low, low): (low, 3)}
print(next(iter(tk)), next(iter(tk.values())), list(iter(tk.items())))
ts = {(big, low), (1, 2)}
print(sorted(iter(ts)), next(iter([((big, 3), 4)])))


class Bag:
    def __init__(self, items: list[int]):
        self.items = items

    def __iter__(self) -> Iterator[int]:
        return iter(self.items)


b = Bag([big, low])
bi = iter(b)
print(next(bi), next(bi), next(bi, 0), list(b), sum(b), list(iter(b)))

print(first(xs), first(t), first(d), first(s), first(ps))
print(drain(xs), drain(d.values()), sorted(drain(s)))
print(pairs_of({big: low, 1: 2}), count(xs), count(d), count(s))
print(keys_of({(big, 1): "a", (low, 2): "b"}))
m = made()
mi = iter(m)
print(next(mi), next(mi), next(mi, None))
