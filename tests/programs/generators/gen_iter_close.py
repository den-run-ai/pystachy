# An object whose __iter__ or __reversed__ yields (#490): the generator that a for loop's
# iterable makes of it, directly or through enumerate(), zip() or reversed(), is closed where the
# loop is left, as CPython closes it once the loop drops it (its finally block runs before the
# code after the loop); so is the one that `in`, any() and all() stop early.
from collections.abc import Iterator


class R:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        try:
            for x in self.xs:
                yield x
        finally:
            print("iter closed")

    def __reversed__(self) -> Iterator[int]:
        try:
            i = len(self.xs) - 1
            while i >= 0:
                yield self.xs[i]
                i -= 1
        finally:
            print("reversed closed")


r = R([1, 2, 3])
for x in r:
    print(x)
    break
print("after for")
for x in reversed(r):
    print(x)
    break
print("after reversed")
for i, x in enumerate(r):
    print(i, x)
    break
print("after enumerate")
for i, x in enumerate(r, 10):
    print(i, x)
    break
print("after enumerate(r, 10)")
for a, b in zip(r, [7, 8, 9]):
    print(a, b)
    break
print("after zip")
for a, b in zip(r, [6, 5]):
    print(a, b)
print("after a zip that ends")
print(2 in r)
print("after in")
print(any(x > 1 for x in r), all(x < 2 for x in r))
print("after any and all")
print(sum(r), max(r))
print("end")
