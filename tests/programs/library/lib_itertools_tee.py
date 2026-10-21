# itertools.tee() (lib/_pystachy_itertools.py): independent iterators over one iterator, which
# reads each item once, when the first of them needs it; the items are kept in links of 57 that
# the iterators share, as in the C module, and a tee of a tee iterator copies it.
import itertools
from itertools import islice, tee
from collections.abc import Iterator


def numbers(n: int) -> Iterator[int]:
    for i in range(n):
        print("  read", i)
        yield i


a, b = tee(numbers(4))
print("made")
print(next(a), next(a), next(b), list(a), list(b), list(a), next(b, -1))
x, y = tee("abc")
print(list(y), list(x))
p, q = tee([1.5, 2.5])
print(next(p), list(q), list(p))

# tee() of a tee iterator copies it: the copies share its links and start where it is
c, d = tee(numbers(3))
print(next(c))
e, f = tee(c)
print(list(e), list(f), list(c), list(d))

# a lookahead, as the documentation's recipe
source = iter("abcdef")
[it] = tee(source, 1)
print(next(it))
[fork] = tee(it, 1)
print(next(fork), next(it), next(it))

# more items than one link holds, read in turn and by one iterator ahead of the other
big1, big2 = tee(list(range(200)))
print(sum(big1), next(big2), sum(big2))
lead, lag = tee(itertools.count())
print(list(islice(lead, 120))[-1], next(lag), next(lead), next(lag))
many = tee("xyz", 3)
print(len(many), [list(t) for t in many])
three = tee(numbers(2), 3)
print([next(t) for t in three], [list(t) for t in three])
print(len(tee("ab", 1)), len(tee(numbers(1), 0)))
try:
    tee("abc", -1)
except ValueError as err:
    print("ValueError:", err)
try:
    tee("abc", 1.0)
except TypeError as err:
    print("TypeError:", err)
r, s = tee(numbers(3))
for item in r:
    print("r", item, "s", next(s))
print(list(s))
u, v = tee(numbers(2))
print(list(u.__copy__()), list(v), list(u))
