# itertools.islice() (lib/_pystachy_itertools.py): the C type's arguments (stop; start, stop and
# step; None for any), its ValueErrors when it is called, and the items it reads: those before
# each one it returns, none past stop, so the iterator it shares goes on after them.
from itertools import count, islice
from collections.abc import Iterator


def numbers(n: int) -> Iterator[int]:
    for i in range(n):
        print("  read", i)
        yield i


s = "ABCDEFG"
print(list(islice(s, 2)), list(islice(s, 2, 4)), list(islice(s, 2, None)), list(islice(s, 0, None, 2)))
print(list(islice(s, None)), list(islice(s, None, 3)), list(islice(s, 1, None, None)), list(islice(s, 5, 2)))
print(list(islice(s, 0)), list(islice(s, 100)), list(islice(s, 3, 100, 2)), list(islice(s, True, 3)))
print(list(islice([1, 2, 3], 1, 3)), list(islice((1.5, 2.5), 1)), list(islice({"a": 1, "b": 2}, 1, 2)))
print(list(islice(count(), 2, 20, 5)), list(islice(count(1), 0, 3)))
stop: int | None = None
print(list(islice(s, 4, stop)))
stop = 3
print(list(islice(s, stop)))

# what it reads: up to max(start, stop) items, and no more
it = iter([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
print(list(islice(it, 3)), next(it))
it = iter([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
print(list(islice(it, 1, 6, 3)), next(it))
it = iter([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
print(list(islice(it, 4, 2)), next(it))
it = iter([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
print(list(islice(it, 0)), next(it))
g = numbers(10)
sl = islice(g, 2, 7, 2)
print("made")
for x in sl:
    print("got", x)
print("after", next(g))
g2 = numbers(3)
print(list(islice(g2, 1, None)))
print(list(islice(g2, 5)))
first_two = islice(numbers(5), 2)
print(next(first_two), next(first_two), next(first_two, -1), next(first_two, -1))

# arguments: CPython's ValueErrors (and TypeErrors for their number), before any item is read
try:
    islice(numbers(3), -1)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(numbers(3), -2)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(s, -1, 3)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(s, 1, -1)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(s, 1, -5)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(s, 0, 3, 0)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(s, 0, 3, -1)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(s, 2.5)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(s, "a", 3)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(s, 1, 3, 1.5)
except ValueError as e:
    print("ValueError:", e)
try:
    islice(s)
except TypeError as e:
    print("TypeError:", e)
try:
    islice(s, 1, 2, 3, 4)
except TypeError as e:
    print("TypeError:", e)
