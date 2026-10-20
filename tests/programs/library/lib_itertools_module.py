# The itertools module (lib/_pystachy_itertools.py, which Pystachy loads for import itertools, as
# CPython imports its C module): its docstring, names by attribute, by from-import and by
# import *, functions as values, chain's repr and chain.from_iterable as a bound method.
import itertools
import itertools as it
from itertools import *

print(itertools.__doc__.splitlines()[0])
print(itertools.__name__, it.__name__)
print(list(it.islice(it.count(5), 3)), list(islice(count(5), 3)), list(itertools.repeat("r", 2)))
print(itertools.chain, it.chain is chain, repr(chain))
flatten = chain.from_iterable
print(list(flatten([[1, 2], [3]])), list(it.chain.from_iterable(["ab", "c"])))
take = islice
print(list(take("abcdef", 1, 4)))
pick = compress
print(list(pick("abc", [0, 1, 1])))
print(product.__name__, combinations.__name__, groupby.__name__)


def apply(f, xs: list[int]) -> list[int]:
    return list(f(xs))


print(apply(accumulate, [1, 2, 3]), apply(cycle, []))
print([list(g) for g in tee([1, 2])], list(zip_longest("a", "bc")), list(starmap(max, [(1, 2)])))
print(list(dropwhile(lambda x: x < 2, [1, 2, 3])), list(takewhile(lambda x: x < 2, [1, 2, 3])))
print(list(filterfalse(None, [0, 1])), list(batched("abc", 2)), list(permutations("ab")))
print(list(combinations_with_replacement("ab", 2)))
