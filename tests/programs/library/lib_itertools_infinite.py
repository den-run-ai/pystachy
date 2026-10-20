# itertools' infinite iterators (lib/_pystachy_itertools.py): count(), cycle() and repeat(), cut
# short by islice(), zip(), takewhile() and break; their argument checks raise CPython's errors
# when they are called, before any item is taken.
import itertools
from itertools import count, cycle, islice, repeat, takewhile
from collections.abc import Iterator


def take(n: int, it):
    # the first n items, as test_itertools' take()
    return list(islice(it, n))


def letters(word: str) -> Iterator[str]:
    for c in word:
        print("  read", c)
        yield c


# count(): ints, floats and the types CPython's C counter gives a bool start or a float step
print(take(5, count()), take(3, count(10)), take(3, count(start=-3)), take(3, count(step=-2)))
print(take(4, count(2.5, 0.5)), take(3, count(0.5, 1)), take(4, count(1, 0.25)), take(3, count(-1, -1.5)))
print(take(3, count(True)), take(3, count(True, 2)), take(3, count(False, True)), take(3, count(True, 0.5)))
print(take(3, count(5, True)), take(3, count(5, False)), take(3, count(7, 0)), take(3, count(0.0, 0)))
c = count(3)
print(next(c), next(c), next(c))
for i, ch in zip(count(1), "abc"):
    print(i, ch)
print(list(takewhile(lambda x: x < 20, count(1, 7))))
total = 0
for k in count():
    if k > 100:
        break
    total += k
print(total)
print(sum(x for x in takewhile(lambda x: x < 1.0, count(0.0, 0.125))))
try:
    count("a")
except TypeError as e:
    print("TypeError:", e)
try:
    count(0, "b")
except TypeError as e:
    print("TypeError:", e)

# cycle(): items as they are read, then the saved copy again and again
print(take(10, cycle("abc")), take(5, cycle([1, 2])), take(3, cycle((7.5,))))
cy = cycle(letters("xy"))
print("made")
print(next(cy), next(cy), next(cy), next(cy), next(cy))
empty: list[int] = []
print(list(cycle(empty)), list(cycle("")))
d = {"k": 1, "j": 2}
print(take(5, cycle(d)), take(4, cycle({3})))
saved = [1, 2, 3]
sc = cycle(saved)
print(next(sc), next(sc))
saved.append(4)  # (read through the list's iterator, which sees it)
print(take(6, sc))

# repeat(): times by position or name, a negative or zero number of times, or endlessly
print(list(repeat("a", 3)), list(repeat(7, times=2)), list(repeat(1, 0)), list(repeat(1, -5)))
print(list(repeat([1], 2)), list(repeat(object=2.5, times=2)), list(repeat(True, True)))
print(take(4, repeat("z")), list(zip(repeat(0), "ab")), list(map(pow, [1, 2, 3], repeat(2))))
shared = [0]
r = list(repeat(shared, 3))
r[0].append(1)
print(r, r[1] is shared)
rr = repeat(5, 2)
print(next(rr), next(rr), next(rr, -1))
try:
    repeat(1, None)
except TypeError as e:
    print("TypeError:", e)
try:
    repeat(1, times=2.0)
except TypeError as e:
    print("TypeError:", e)
try:
    repeat(1, "3")
except TypeError as e:
    print("TypeError:", e)
print(itertools.__name__, count.__name__, repeat.__name__)
