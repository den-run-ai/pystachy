# itertools.zip_longest() (lib/_pystachy_itertools.py): tuples of an item of each iterable, which
# may have types of their own, filled with fillvalue (None, or a value of the items' type) once an
# iterable has finished; a finished iterator is not read again, and the last one ends it.
from itertools import count, islice, zip_longest
from collections.abc import Iterator


def letters(word: str) -> Iterator[str]:
    for c in word:
        print("  read", c)
        yield c


print(list(zip_longest("ABCD", "xy", fillvalue="-")), list(zip_longest("ABCD", [1, 2])))
print(list(zip_longest([1, 2, 3], [4], fillvalue=0)), list(zip_longest([1.5], (2.5, 3.5), fillvalue=0.0)))
print(list(zip_longest([1, 2, 3], "ab", [True])), list(zip_longest("a")), list(zip_longest()))
print(list(zip_longest("ab", "cd", "e", "fgh")), list(zip_longest([1], [2], [3], [4], [5, 6], fillvalue=-1)))
empty: list[int] = []
print(list(zip_longest(empty, empty)), list(zip_longest(empty, [1])), list(zip_longest({"k": 1}, {7})))
print(list(islice(zip_longest(count(), "ab"), 4)), list(zip(zip_longest("ab", "c"), count())))
for left, right in zip_longest([1, 2, 3], ["x"]):
    print(left, right)
z = zip_longest(letters("ab"), letters("c"))
print("made")
print(next(z))
print(list(z), list(z))
pairs = list(zip_longest("abc", [0, 1], fillvalue=None))
print(pairs, pairs[2] == ("c", None))
