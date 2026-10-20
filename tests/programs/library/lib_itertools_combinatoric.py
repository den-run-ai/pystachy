# itertools' combinatoric iterators (lib/_pystachy_itertools.py): product(), permutations(),
# combinations() and combinations_with_replacement() read the whole of their iterables when they
# are called, as the C types do, and yield tuples in CPython's order. product() without repeat
# yields a tuple of an item of each iterable, of its type; the others' tuples (and product()'s
# with repeat) have a length known as the program runs, of items of one type.
from itertools import combinations, combinations_with_replacement, permutations, product
from collections.abc import Iterator
import math


def numbers(n: int) -> Iterator[int]:
    for i in range(n):
        print("  read", i)
        yield i


empty: list[int] = []

# product()
print(list(product("AB", "xy")), list(product("ab", [1, 2], [True])), list(product([0.5])))
print(list(product([0, 1], repeat=3)), list(product("ab", repeat=2)), list(product("ab", "c", repeat=2)))
print(list(product()), list(product(repeat=4)), list(product([1, 2], repeat=0)), list(product(empty, [1])), list(product([1], empty, repeat=2)))
print(list(product("ab", "cd", "e", "fg")), len(list(product([1, 2, 3], [4, 5], "ab", "cd", [True]))))
for x, y in product([1, 2], ["a", "b"]):
    print(x, y)
for t in product([1, 2], repeat=2):
    a, b = t
    print(a + b, t[0], len(t))
print(sorted(product([2, 1], [0])), list(product({"k": 1}, {3})), list(product((1.5, 2.5), repeat=1)))
pr = product(numbers(2), numbers(2))
print("made")
print(list(pr))
pr2 = product(numbers(2), repeat=0)
print("made")
print(list(pr2))
try:
    product("ab", repeat=-1)
except ValueError as e:
    print("ValueError:", e)
try:
    product("ab", repeat=1.0)
except TypeError as e:
    print("TypeError:", e)

# permutations()
print(list(permutations("ABC", 2)), list(permutations([1, 2, 3])), list(permutations("ab", 3)))
print(list(permutations(empty)), list(permutations("ab", 0)), list(permutations(empty, 0)), list(permutations((True, False), None)))
print(len(list(permutations(list(range(6)), 4))) == math.perm(6, 4), list(permutations([1.5, 2.5], r=1)))
pm = permutations(numbers(3), 2)
print("made")
print(list(pm))
try:
    permutations(numbers(2), -1)
except ValueError as e:
    print("ValueError:", e)
try:
    permutations(numbers(2), 1.0)
except TypeError as e:
    print("TypeError:", e)

# combinations() and combinations_with_replacement()
print(list(combinations("ABCD", 2)), list(combinations([0, 1, 2, 3], 3)), list(combinations("ab", 3)))
print(list(combinations("ab", 0)), list(combinations(empty, 0)), list(combinations([1, 2], r=2)))
print(list(combinations_with_replacement("ABC", 2)), list(combinations_with_replacement([1, 2], 3)))
print(list(combinations_with_replacement(empty, 0)), list(combinations_with_replacement(empty, 2)), list(combinations_with_replacement("a", 0)))
for n in range(5):
    for r in range(6):
        c1 = len(list(combinations(list(range(n)), r)))
        c2 = len(list(combinations_with_replacement(list(range(n)), r)))
        c3 = len(list(permutations(list(range(n)), r)))
        assert c1 == math.comb(n, r) and c3 == math.perm(n, r), (n, r)
        assert c2 == (math.comb(n + r - 1, r) if n else (1 if r == 0 else 0)), (n, r)
print("counts agree")
cb = combinations(numbers(4), 2)
print("made")
print(next(cb), list(cb))
cw = combinations_with_replacement(numbers(2), 2)
print("made")
print(list(cw))
for size in (-1, -2):
    try:
        combinations(numbers(2), size)
    except ValueError as e:
        print("ValueError:", e)
    try:
        combinations_with_replacement(numbers(2), size)
    except ValueError as e:
        print("ValueError:", e)
try:
    combinations(numbers(2), 2.0)
except TypeError as e:
    print("TypeError:", e)
words = ["red", "green", "blue"]
print([" ".join(c) for c in combinations(words, 2)], ["".join(p) for p in permutations("ab")])
print([sum(c) for c in combinations([1, 2, 3, 4], 2)], max(product([1, 2], [3, 4])))
