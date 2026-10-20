# itertools with generators and generator expressions (lib/_pystachy_itertools.py): their inputs
# are read lazily, one item at a time, so infinite inputs end where islice(), zip(), takewhile()
# or break stop reading; itertools inside generator functions and generator expressions; an
# exception from an input reaches the consumer.
from itertools import (accumulate, batched, chain, compress, count, cycle, dropwhile, filterfalse, groupby, islice,
                       pairwise, product, repeat, starmap, takewhile, tee, zip_longest)
from collections.abc import Iterator


def gen(n: int) -> Iterator[int]:
    for i in range(n):
        print("  gen", i)
        yield i


def evens() -> Iterator[int]:
    yield from filterfalse(lambda x: x % 2, count())


def windows(xs: list[str]) -> Iterator[str]:
    for a, b in pairwise(xs):
        yield a + b


def failing(n: int) -> Iterator[int]:
    for i in range(n):
        yield i
    raise ValueError("input failed")


# generator expressions as inputs, finite and infinite
print(list(chain((x * x for x in range(3)), [9])))
print(list(islice((x for x in count()), 5)))
print(list(islice(accumulate(count(1)), 4)))
print(list(islice(dropwhile(lambda x: x < 5, count()), 3)))
print(list(islice(filterfalse(lambda x: x % 3, count()), 3)))
print(list(takewhile(lambda x: x < 4, count())))
print(list(islice(pairwise(count()), 3)))
print(list(islice(starmap(lambda a, b: a * b, ((i, i + 1) for i in count())), 4)))
print(list(islice(compress(count(), cycle([True, False])), 4)))
print(list(islice(zip_longest(count(), "ab"), 4)))
print(list(islice(chain.from_iterable(repeat([1, 2])), 5)))
print(list(islice(batched(count(), 2), 3)))
print([(k, list(g)) for k, g in islice(groupby(cycle("aab")), 4)])
print(list(islice(takewhile(lambda t: t < 50, accumulate(x * x for x in count(1))), 10)))

# zip(), enumerate() and loops with break over infinite iterators
for x, y in zip(count(10), "abc"):
    print(x, y)
for i, t in zip(range(3), tee(count())[1]):
    print(i, t)
for i, v in enumerate(cycle("xy")):
    if i == 4:
        break
    print(i, v)

# generators read one item at a time: islice() stops reading at stop, and the generator goes on
it = gen(5)
print(list(islice(it, 2)))
print(next(it))
print(list(islice(gen(10), 1, 6, 2)))
g = (i * 2 for i in gen(4))
print(list(pairwise(g)))
print(sum(accumulate(gen(4))))
print(max(chain(gen(2), gen(3))))
print(list(product(gen(2), gen(2))))
for k, grp in groupby(gen(6), lambda x: x // 2):
    print("key", k)
    print("group", list(grp))

# itertools inside generator functions and generator expressions
print(list(islice(evens(), 4)), list(windows(["a", "b", "c", "d"])))
print(sum(x for x in islice(count(), 5)), [b for b in batched((c.upper() for c in "abcde"), 2)])
print(any(x > 3 for x in accumulate(gen(4))), all(x < 10 for x in islice(count(), 5)))
squares = (n * n for n in count())
print(next(squares), list(islice(squares, 3)), next(squares))

# an exception from an input reaches the consumer
try:
    for w in chain([10], failing(2)):
        print("chain", w)
except ValueError as e:
    print("ValueError:", e)
try:
    print(list(accumulate(failing(3))))
except ValueError as e:
    print("ValueError:", e)
try:
    print(list(islice(failing(1), 5)))
except ValueError as e:
    print("ValueError:", e)
print(list(islice(failing(5), 3)))
