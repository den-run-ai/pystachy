# pystachy: python-int
# heapq and bisect, modules of lib/ that do not opt in, keep the ints past 64 bits of the lists that
# they change in place, which every name for such a list sees: heappush(), heappop(), heapify(),
# heapreplace(), heappushpop(), nsmallest() and nlargest() (of lists and of a generator, with and
# without a key) and the bisect and insort functions (with and without a key), on lists of ints and
# of tuples of ints; and a module that does not opt in (fixed_heaps) that hands them such a list.
import bisect
import heapq

from fixed_heaps import pop_two, push_range, where

big = 2 ** 64
low = -2 ** 63
h: list[int] = []
for x in [big, 5, -big, low, 2 ** 100, 0, big + 1]:
    heapq.heappush(h, x)
alias = h
print(h[0], len(h), alias is h)
print([heapq.heappop(h) for _ in range(3)], alias)
heapq.heappush(h, -(2 ** 70))
print(heapq.heapreplace(h, 2 ** 65), heapq.heappushpop(h, -1), heapq.heappushpop(h, 2 ** 200), alias)
xs = [big * 3, 1, big, low, -big, 7, low - 1]
ys = list(xs)
heapq.heapify(xs)
print(xs[0], [heapq.heappop(xs) for _ in range(len(ys))] == sorted(ys), xs)

data = [big, 3, -big, low, 2 ** 90, 0, big - 1]
print(heapq.nsmallest(3, data), heapq.nlargest(3, data), heapq.nsmallest(1, data), heapq.nlargest(1, data))
print(heapq.nsmallest(10, data), heapq.nlargest(0, data))


def neg(v: int) -> int:
    return -v


print(heapq.nsmallest(2, data, key=neg), heapq.nlargest(2, data, key=lambda v: -v), heapq.nsmallest(1, data, key=abs))


def gen(n: int):
    yield n
    yield n + 1
    yield -n


print(heapq.nlargest(1, gen(big)), heapq.nsmallest(2, gen(big)), heapq.nlargest(2, gen(2 ** 70)))

pq: list[tuple[int, str]] = []
heapq.heappush(pq, (big, "b"))
heapq.heappush(pq, (low, "l"))
heapq.heappush(pq, (2 ** 70, "x"))
heapq.heappush(pq, (big, "a"))
print(heapq.heappop(pq), heapq.heappop(pq), pq)
pairs = [(big, 1), (big, 0), (-big, 5), (3, low)]
heapq.heapify(pairs)
print(heapq.heappop(pairs), heapq.nsmallest(2, pairs), heapq.nlargest(1, pairs))

a = [-big, low, 0, big, 2 ** 80]
b2 = a
print(bisect.bisect_left(a, big), bisect.bisect_right(a, big), bisect.bisect(a, -(2 ** 70)), bisect.bisect_left(a, 2 ** 81))
bisect.insort(a, big + 5)
bisect.insort_left(a, -(2 ** 90))
bisect.insort_right(a, big)
print(a, b2 is a)
print(bisect.bisect_left(a, big, 2), bisect.bisect_right(a, big, 0, 3))
ps = [(low, 0), (1, 2), (big, 1)]
bisect.insort(ps, (big, 0))
print(ps, bisect.bisect_left(ps, (big, 1)))
down = [big, 0, -big]  # (in order of neg())
bisect.insort(down, 2 ** 70, key=neg)
bisect.insort_left(down, -(2 ** 70), key=neg)
print(down, bisect.bisect_left([(1, -big), (2, big)], 0, key=lambda p: p[1] // big), bisect.bisect_right(down, -big, key=neg))

hh = [big, 2 ** 70]
heapq.heapify(hh)
push_range(hh, 3)
print(hh[0], len(hh), pop_two(hh), where(sorted(hh), 1), hh)
