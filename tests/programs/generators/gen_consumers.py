# A generator where an iterable is taken (#490): sum(), min(), max(), any() and all() take its
# items as they come (any() and all() stop at the deciding one), list(), sorted(), tuple(),
# set(), frozenset(), str.join() and list.extend() take them all; in and not in stop at a match;
# enumerate(), zip() and comprehensions iterate it.
from collections.abc import Iterator


def squares(n: int) -> Iterator[int]:
    for i in range(n):
        yield i * i


def names() -> Iterator[str]:
    yield "carol"
    yield "alice"
    yield "bob"


def seen(n: int) -> Iterator[int]:
    for i in range(n):
        print("  produce", i)
        yield i


def halves(n: int) -> Iterator[float]:
    for i in range(n):
        yield i / 2


print(sum(squares(5)), sum(squares(4), 10), sum(halves(4)))
print(list(squares(4)), sorted(names()), sorted(names(), reverse=True))
print(any(seen(10)))
print(all(seen(3)))
print(any(x > 3 for x in seen(10)))
print(max(squares(6)), min(names()), max(names(), key=len), min(halves(3)))
print(tuple(squares(3)), sorted(set(names())), sorted(frozenset(squares(3))))
print(", ".join(names()))
print(9 in squares(10), 10 in squares(10), "bob" not in names())
print(4 in seen(10))
acc = [0]
acc.extend(squares(3))
print(acc)
for i, n in enumerate(names()):
    print(i, n)
for i, n in enumerate(names(), 1):
    print(i, n)
for a, b in zip(names(), squares(10)):
    print(a, b)
for p, q in zip(seen(5), [10, 20]):
    print("zipped", p, q)
print([s + 1 for s in squares(4)], {s % 3 for s in squares(5)})
print(sorted(n.upper() for n in names()), sum(s for s in squares(4) if s % 2 == 0))
print(len(list(squares(7))), list(squares(0)), sum(squares(0)))
total = 0
for s in squares(1000):
    total += s
print(total)
