# Adapted from CPython 3.13.16 Lib/test/test_itertools.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91 (SHA-256
# b356e71312eaac265c7104c32176c5150ab06433754bcb25d6e0013f321ca1c9): class TestBasicOps's
# test_accumulate, test_batched, test_chain, test_chain_from_iterable, test_combinations,
# test_combinations_with_replacement, test_permutations, test_combinatorics, test_compress,
# test_count, test_count_with_step, test_cycle, test_groupby, test_filterfalse, test_ziplongest,
# test_bug_7244, test_pairwise, test_product, test_repeat, test_starmap, test_islice,
# test_takewhile, test_dropwhile, test_tee, test_tee_reenter and test_StopIteration; class
# TestExamples's tests of itertools; TestPurePythonRoughEquivalents.test_batched_recipe; class
# TestVariousIteratorArgs's tests of itertools; RegressionTests.test_sf_950057 and
# test_long_chain_of_empty_iterables.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name (a class's own tests are prefixed with
# the class); assertEqual(a, b) prints a and asserts a == b, assertTrue(x) asserts x, and
# assertRaises(E, f, ...) is a try statement that prints the error. Loops over many cases assert
# without printing. Ranges are values, as upstream; lzip(a, b) is list(zip(a, b)); fact() is
# math.factorial(); a loop over islice()'s argument tuples slices a list of a range; an empty list
# that nothing types is an annotated variable. A loop over helper classes or functions (G, I,
# Ig, S, L, R; chain, cycle, ...) is a statement for each, and a loop over test values of
# different types (("123", "", range(1000), ...)) a call of a function for each; L() is
# chain() of a generator expression over R(Ig(...)), as map() is not a value; test_starmap's
# values are those whose powers x ** x fit in 64 bits (range(10), range(0), (7, 11)). product(*args)
# of a list of pools, whose number only the run time knows, is product(*pools, repeat=1) of
# a list of lists, and test_product's random argument lists are lists of strs. E's __next__
# returns 3 // 0. tee(iterable, n) is a list (tests/deviations/lib_itertools_tee_list.py).
# Upstream's sizes where a case is about size: make verify runs this program with a collection at
# every allocation (gc-stress), where each allocation scans the live heap, so the same code runs
# on smaller inputs: test_combinations_with_replacement and test_permutations for n < 6 (not 7),
# test_combinatorics for n < 5 and r < 7 (not 6 and 8), test_product's length of a product of
# 5 ** 4 tuples (not 7 ** 6), and test_long_chain_of_empty_iterables over 10 ** 4 empty
# iterables (not 10 ** 7).
# EXCLUDED upstream cases:
# - pickling, copy and deepcopy (pickletest, the *_reducible and *_pickling tests, setstate),
#   weak references, sys.getsizeof (SizeofTest), the threading tests, the TestGC cycles and the
#   *_result_gc and *_tuple_reuse tests (CPython's object identities and reference counts), the
#   overflow tests (bigaddrspacetest), test_immutable_types and SubclassWithKwargsTest (class
#   attributes and subclasses of itertools' types, which are functions here)
# - reprs: count(3), repeat('a', 0) (itertools' iterators are generators, which do not print:
#   tests/errors/library/lib_itertools_print.py)
# - ints past 64 bits (maxsize + 1, 1 << 1000), complex numbers, Decimal and Fraction
# - wrong numbers or kinds of arguments, which are compile-time errors here: too few or many
#   arguments, keyword arguments a function has not, non-iterables (None, 3, X, N), arguments
#   of types the function does not take (accumulate([1, []]), chain(2, 3), groupby('abc',
#   []), starmap(operator.pow, [None]), functions of the wrong arity (chr, onearg), non-callable
#   predicates (10)); test_zip_longest_bad_iterable (an __iter__ that only raises has no type)
# - G, the sequence class iterated through __getitem__ alone, and ('do', 1.2), a tuple whose
#   items differ; test_ziplongest's tuples of 5 or 6 ranges built from args (a tuple of more
#   than four items of different lengths: zip_longest(*args) of a list), and the eval() of
#   statements with bogus keywords
# - test_groupby_reentrant_eq_does_not_crash, test_grouper_reentrant_eq_does_not_crash,
#   test_pairwise_reenter, test_pairwise_reenter2, test_issue30347_1 and test_issue30347_2: an
#   itertools iterator resumed from inside its own key, __eq__ or input raises "generator already
#   executing" here (lib/compatibility.md); test_groupby's DummyCmp (an __eq__ that only raises)
#   and the keyfunc with an attribute (function attributes); test_accumulate_reducible_none (a
#   list of None)
# - test_filter, test_zip, test_map and TestExamples' test_filter, test_map and test_zip (the
#   builtins, which tests/programs/upstream/upstream_builtin_*.py adopt), test_tee's type(a)('def') (a class as a
#   value), its long-lagged del of an iterator (del does not free here), TestPurePythonRough-
#   Equivalents' islice and tee recipes (pure Python versions, not itertools), LengthTransparency
#   (operator.length_hint), test_tee_dealloc_segfault and test_tee_del_backward (CPython's
#   deallocation), test_sf_793826 (zip(*[gen]*n) and map() as values)
import math
import operator
from functools import reduce
from itertools import (accumulate, batched, chain, combinations, combinations_with_replacement, compress, count,
                       cycle, dropwhile, filterfalse, groupby, islice, pairwise, permutations, product, repeat,
                       starmap, takewhile, tee, zip_longest)
from collections.abc import Iterator
import random

maxsize = 9223372036854775807


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_empty(label: str, got) -> None:
    # check(label, got, []), where the empty list has the type of got
    print(label, repr(got))
    assert len(got) == 0, label


def strs(xs: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    # a list display of tuples, as tuples of a length known as the program runs, which the
    # combinatoric functions yield
    return xs


def ints(xs: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    return xs


def gen3() -> Iterator[int]:
    'Non-restartable source sequence'
    for i in (0, 1, 2):
        yield i


def isEven(x: int) -> bool:
    'Test predicate'
    return x % 2 == 0


def isOdd(x: int) -> bool:
    'Test predicate'
    return x % 2 == 1


def irange(n: int) -> Iterator[int]:
    for i in range(n):
        yield i


class StopNow:
    'Class emulating an empty iterable.'
    def __iter__(self):
        return self

    def __next__(self) -> int:
        raise StopIteration


def take(n: int, seq):
    'Convenience function for partially consuming a long of infinite iterable'
    return list(islice(seq, n))


def prod(iterable: list[int]) -> int:
    return reduce(operator.mul, iterable, 1)


def fact(n: int) -> int:
    'Factorial'
    return prod(list(range(1, n + 1)))


def testR(r: tuple[int, int, int]) -> int:
    return r[0]


def testR2(r: tuple[int, int, int]) -> int:
    return r[2]


def underten(x: int) -> bool:
    return x < 10


def errfunc(x: int) -> bool:
    'Test function that raises an error'
    raise ValueError


# --- TestBasicOps ---

def test_accumulate() -> None:
    check("accumulate(range(10))", list(accumulate(range(10))), [0, 1, 3, 6, 10, 15, 21, 28, 36, 45])
    check("iterable=", list(accumulate(iterable=range(10))), [0, 1, 3, 6, 10, 15, 21, 28, 36, 45])
    check("abc", list(accumulate('abc')), ['a', 'ab', 'abc'])
    empty: list[int] = []
    check("[]", list(accumulate(empty)), empty)
    check("[7]", list(accumulate([7])), [7])
    s = [2, 8, 9, 5, 7, 0, 3, 4, 1, 6]
    check("min", list(accumulate(s, min)), [2, 2, 2, 2, 2, 0, 0, 0, 0, 0])
    check("max", list(accumulate(s, max)), [2, 8, 9, 9, 9, 9, 9, 9, 9, 9])
    check("mul", list(accumulate(s, operator.mul)), [2, 16, 144, 720, 5040, 0, 0, 0, 0, 0])
    check("initial=None", list(accumulate([10, 5, 1], initial=None)), [10, 15, 16])
    check("initial=100", list(accumulate([10, 5, 1], initial=100)), [100, 110, 115, 116])
    check("[] initial", list(accumulate(empty, initial=100)), [100])


def test_batched() -> None:
    want3: list[tuple[str, ...]] = [('A', 'B', 'C'), ('D', 'E', 'F'), ('G',)]
    check("3", list(batched('ABCDEFG', 3)), want3)
    want2: list[tuple[str, ...]] = [('A', 'B'), ('C', 'D'), ('E', 'F'), ('G',)]
    check("2", list(batched('ABCDEFG', 2)), want2)
    want1: list[tuple[str, ...]] = [('A',), ('B',), ('C',), ('D',), ('E',), ('F',), ('G',)]
    check("1", list(batched('ABCDEFG', 1)), want1)
    wants: list[tuple[str, ...]] = [('A', 'B'), ('C', 'D'), ('E', 'F')]
    check("strict", list(batched('ABCDEF', 2, strict=True)), wants)
    try:
        list(batched('ABCDEFG', 3, strict=True))
    except ValueError as e:
        print("ValueError", e)
    try:
        list(batched('ABCDEFG', 'hello'))
    except TypeError as e:
        print("TypeError", e)
    try:
        list(batched('ABCDEFG', 0))
    except ValueError as e:
        print("ValueError", e)
    try:
        list(batched('ABCDEFG', -1))
    except ValueError as e:
        print("ValueError", e)
    data = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    for n in range(1, 6):
        for i in range(len(data)):
            s = data[:i]
            batches = list(batched(s, n))
            # Order is preserved and no data is lost
            assert ''.join(chain.from_iterable(batches)) == s
            # All but the last batch is of size n
            if batches:
                last_batch = batches.pop()
                assert all(len(batch) == n for batch in batches)
                assert len(last_batch) <= n
                batches.append(last_batch)
    print("batches checked")


def chain2(*iterables):
    'Pure python version in the docs'
    for it in iterables:
        for element in it:
            yield element


def test_chain() -> None:
    check("chain", list(chain('abc', 'def')), list('abcdef'))
    check("chain 1", list(chain('abc')), list('abc'))
    check_empty("chain ''", list(chain('')))
    check("take", take(4, chain('abc', 'def')), list('abcd'))
    check("chain2", list(chain2('abc', 'def')), list('abcdef'))
    check("chain2 1", list(chain2('abc')), list('abc'))
    check_empty("chain2 ''", list(chain2('')))
    check("take chain2", take(4, chain2('abc', 'def')), list('abcd'))


def test_chain_from_iterable() -> None:
    check("from_iterable", list(chain.from_iterable(['abc', 'def'])), list('abcdef'))
    check("one", list(chain.from_iterable(['abc'])), list('abc'))
    check_empty("empty", list(chain.from_iterable([''])))
    check("take", take(4, chain.from_iterable(['abc', 'def'])), list('abcd'))
    check("repeat", list(islice(chain.from_iterable(repeat(range(5))), 2)), [0, 1])


def combinations1(iterable, r: int):
    'Pure python version shown in the docs'
    pool = tuple(iterable)
    n = len(pool)
    if r > n:
        return
    indices = list(range(r))
    yield tuple(pool[i] for i in indices)
    while 1:
        for i in reversed(range(r)):
            if indices[i] != i + n - r:
                break
        else:
            return
        indices[i] += 1
        for j in range(i + 1, r):
            indices[j] = indices[j - 1] + 1
        yield tuple(pool[i] for i in indices)


def combinations2(iterable, r: int):
    'Pure python version shown in the docs'
    pool = tuple(iterable)
    n = len(pool)
    for indices in permutations(range(n), r):
        if sorted(indices) == list(indices):
            yield tuple(pool[i] for i in indices)


def combinations3(iterable, r: int):
    'Pure python version from cwr()'
    pool = tuple(iterable)
    n = len(pool)
    for indices in combinations_with_replacement(range(n), r):
        if len(set(indices)) == r:
            yield tuple(pool[i] for i in indices)


def test_combinations() -> None:
    try:
        combinations('abc', -2)
    except ValueError as e:
        print("ValueError", e)
    check_empty("r > n", list(combinations('abc', 32)))
    check("ABCD 2", list(combinations('ABCD', 2)), strs([('A', 'B'), ('A', 'C'), ('A', 'D'), ('B', 'C'), ('B', 'D'), ('C', 'D')]))
    testIntermediate = combinations('ABCD', 2)
    next(testIntermediate)
    check("intermediate", list(testIntermediate), strs([('A', 'C'), ('A', 'D'), ('B', 'C'), ('B', 'D'), ('C', 'D')]))
    check("range 3", list(combinations(range(4), 3)), ints([(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]))
    testIntermediate2 = combinations(range(4), 3)
    next(testIntermediate2)
    check("intermediate 2", list(testIntermediate2), ints([(0, 1, 3), (0, 2, 3), (1, 2, 3)]))
    for n in range(7):
        values = [5 * x - 12 for x in range(n)]
        for r in range(n + 2):
            result = list(combinations(values, r))
            assert len(result) == (0 if r > n else fact(n) // fact(r) // fact(n - r))  # right number of combs
            assert result == sorted(result)  # lexicographic order
            for c in result:
                assert len(c) == r  # r-length combinations
                assert len(set(c)) == r  # no duplicate elements
                assert list(c) == sorted(c)  # keep original ordering
                assert all(e in values for e in c)  # elements taken from input iterable
                assert list(c) == [e for e in values if e in list(c)]  # comb is a subsequence of the input iterable
            assert result == list(combinations1(values, r))  # matches first pure python version
            assert result == list(combinations2(values, r))  # matches second pure python version
            assert result == list(combinations3(values, r))  # matches second pure python version
    print("combinations checked")


def cwr1(iterable, r: int):
    'Pure python version shown in the docs'
    # number items returned:  (n+r-1)! / r! / (n-1)! when n>0
    pool = tuple(iterable)
    n = len(pool)
    if not n and r:
        return
    indices = [0] * r
    yield tuple(pool[i] for i in indices)
    while 1:
        for i in reversed(range(r)):
            if indices[i] != n - 1:
                break
        else:
            return
        indices[i:] = [indices[i] + 1] * (r - i)
        yield tuple(pool[i] for i in indices)


def cwr2(iterable, r: int):
    'Pure python version shown in the docs'
    pool = tuple(iterable)
    n = len(pool)
    for indices in product(range(n), repeat=r):
        if sorted(indices) == list(indices):
            yield tuple(pool[i] for i in indices)


def numcombs(n: int, r: int) -> int:
    if not n:
        return 0 if r else 1
    return fact(n + r - 1) // fact(r) // fact(n - 1)


def test_combinations_with_replacement() -> None:
    cwr = combinations_with_replacement
    try:
        cwr('abc', -2)
    except ValueError as e:
        print("ValueError", e)
    check("ABC 2", list(cwr('ABC', 2)), strs([('A', 'A'), ('A', 'B'), ('A', 'C'), ('B', 'B'), ('B', 'C'), ('C', 'C')]))
    testIntermediate = cwr('ABC', 2)
    next(testIntermediate)
    check("intermediate", list(testIntermediate), strs([('A', 'B'), ('A', 'C'), ('B', 'B'), ('B', 'C'), ('C', 'C')]))
    for n in range(6):
        values = [5 * x - 12 for x in range(n)]
        for r in range(n + 2):
            result = list(cwr(values, r))
            assert len(result) == numcombs(n, r)  # right number of combs
            assert result == sorted(result)  # lexicographic order
            regular_combs = list(combinations(values, r))  # compare to combs without replacement
            if n == 0 or r <= 1:
                assert result == regular_combs  # cases that should be identical
            else:
                assert all(c in result for c in regular_combs)  # rest should be supersets of regular combs
            for c in result:
                assert len(c) == r  # r-length combinations
                noruns = [k for k, v in groupby(c)]  # combo without consecutive repeats
                assert len(noruns) == len(set(noruns))  # no repeats other than consecutive
                assert list(c) == sorted(c)  # keep original ordering
                assert all(e in values for e in c)  # elements taken from input iterable
                assert noruns == [e for e in values if e in list(c)]  # comb is a subsequence of the input iterable
            assert result == list(cwr1(values, r))  # matches first pure python version
            assert result == list(cwr2(values, r))  # matches second pure python version
    print("combinations_with_replacement checked")


def permutations1(iterable, r=None):
    'Pure python version shown in the docs'
    pool = tuple(iterable)
    n = len(pool)
    rr = n if r is None else r
    if rr > n:
        return
    indices = list(range(n))
    cycles = list(range(n - rr + 1, n + 1))[::-1]
    yield tuple(pool[i] for i in indices[:rr])
    while n:
        for i in reversed(range(rr)):
            cycles[i] -= 1
            if cycles[i] == 0:
                indices[i:] = indices[i + 1:] + indices[i:i + 1]
                cycles[i] = n - i
            else:
                j = cycles[i]
                indices[i], indices[-j] = indices[-j], indices[i]
                yield tuple(pool[i] for i in indices[:rr])
                break
        else:
            return


def permutations2(iterable, r=None):
    'Pure python version shown in the docs'
    pool = tuple(iterable)
    n = len(pool)
    rr = n if r is None else r
    for indices in product(range(n), repeat=rr):
        if len(set(indices)) == rr:
            yield tuple(pool[i] for i in indices)


def test_permutations() -> None:
    try:
        permutations('abc', -2)
    except ValueError as e:
        print("ValueError", e)
    check_empty("r > n", list(permutations('abc', 32)))
    try:
        permutations('abc', 's')
    except TypeError as e:
        print("TypeError", e)
    check("range 2", list(permutations(range(3), 2)), ints([(0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)]))
    for n in range(6):
        values = [5 * x - 12 for x in range(n)]
        for r in range(n + 2):
            result = list(permutations(values, r))
            assert len(result) == (0 if r > n else fact(n) // fact(n - r))  # right number of perms
            assert result == sorted(result)  # lexicographic order
            for p in result:
                assert len(p) == r  # r-length permutations
                assert len(set(p)) == r  # no duplicate elements
                assert all(e in values for e in p)  # elements taken from input iterable
            assert result == list(permutations1(values, r))  # matches first pure python version
            assert result == list(permutations2(values, r))  # matches second pure python version
            if r == n:
                assert result == list(permutations(values, None))  # test r as None
                assert result == list(permutations(values))  # test default r
    print("permutations checked")


def test_combinatorics() -> None:
    # Test relationships between product(), permutations(),
    # combinations() and combinations_with_replacement().
    for n in range(5):
        s = 'ABCDEFG'[:n]
        for r in range(7):
            prd = list(product(s, repeat=r))
            cwr = list(combinations_with_replacement(s, r))
            perm = list(permutations(s, r))
            comb = list(combinations(s, r))

            # Check size
            assert len(prd) == n ** r
            assert len(cwr) == ((fact(n + r - 1) // fact(r) // fact(n - 1)) if n else int(not r))
            assert len(perm) == (0 if r > n else fact(n) // fact(n - r))
            assert len(comb) == (0 if r > n else fact(n) // fact(r) // fact(n - r))

            # Check lexicographic order without repeated tuples
            assert prd == sorted(prd) and all(prd[i] != prd[i + 1] for i in range(len(prd) - 1))
            assert cwr == sorted(cwr) and all(cwr[i] != cwr[i + 1] for i in range(len(cwr) - 1))
            assert perm == sorted(perm) and all(perm[i] != perm[i + 1] for i in range(len(perm) - 1))
            assert comb == sorted(comb) and all(comb[i] != comb[i + 1] for i in range(len(comb) - 1))

            # Check interrelationships
            assert cwr == [t for t in prd if sorted(t) == list(t)]  # cwr: prods which are sorted
            assert perm == [t for t in prd if len(set(t)) == r]  # perm: prods with no dups
            assert comb == [t for t in perm if sorted(t) == list(t)]  # comb: perms that are sorted
            assert comb == [t for t in cwr if len(set(t)) == r]  # comb: cwrs without dups
            assert comb == [t for t in perm if t in cwr]  # comb: perm that is a cwr
            assert comb == [t for t in cwr if t in perm]  # comb: cwr that is a perm
    print("combinatorics checked")


def test_compress() -> None:
    check("keywords", list(compress(data='ABCDEF', selectors=[1, 0, 1, 0, 1, 1])), list('ACEF'))
    check("ACEF", list(compress('ABCDEF', [1, 0, 1, 0, 1, 1])), list('ACEF'))
    check("none", list(compress('ABCDEF', [0, 0, 0, 0, 0, 0])), list(''))
    check("all", list(compress('ABCDEF', [1, 1, 1, 1, 1, 1])), list('ABCDEF'))
    check("short selectors", list(compress('ABCDEF', [1, 0, 1])), list('AC'))
    check("short data", list(compress('ABC', [0, 1, 1, 1, 1, 1])), list('BC'))
    n = 10000
    data = chain.from_iterable(repeat(range(6), n))
    selectors = chain.from_iterable(repeat([0, 1]))
    check("long", list(compress(data, selectors)) == [1, 3, 5] * n, True)


def test_count() -> None:
    check("lzip", list(zip('abc', count())), [('a', 0), ('b', 1), ('c', 2)])
    check("lzip 3", list(zip('abc', count(3))), [('a', 3), ('b', 4), ('c', 5)])
    check("take 2", take(2, list(zip('abc', count(3)))), [('a', 3), ('b', 4)])
    check("-1", take(2, [p for p in zip('abc', count(-1))]), [('a', -1), ('b', 0)])
    check("-3", take(2, [p for p in zip('abc', count(-3))]), [('a', -3), ('b', -2)])
    try:
        count('a')
    except TypeError as e:
        print("TypeError", e)
    check("3.25", take(3, count(3.25)), [3.25, 4.25, 5.25])
    c = count(-9)
    next(c)
    check("next", next(c), -8)
    check("float type", isinstance(next(count(10.0)), float), True)


def test_count_with_step() -> None:
    check("2, 3", list(zip('abc', count(2, 3))), [('a', 2), ('b', 5), ('c', 8)])
    check("keywords", list(zip('abc', count(start=2, step=3))), [('a', 2), ('b', 5), ('c', 8)])
    check("step=-1", list(zip('abc', count(step=-1))), [('a', 0), ('b', -1), ('c', -2)])
    try:
        count('a', 'b')
    except TypeError as e:
        print("TypeError", e)
    check("2, 0", list(zip('abc', count(2, 0))), [('a', 2), ('b', 2), ('c', 2)])
    check("2, 1", list(zip('abc', count(2, 1))), [('a', 2), ('b', 3), ('c', 4)])
    check("2, 3", list(zip('abc', count(2, 3))), [('a', 2), ('b', 5), ('c', 8)])
    check("-maxsize", take(3, count(-maxsize, maxsize)), [-maxsize, 0, maxsize])
    mixed: list[int | float] = [2, 3.25, 4.5]
    check("1.25", take(3, count(2, 1.25)), mixed)
    mixed2: list[int | float] = [10, 12.5, 15.0]
    check("repr", repr(take(3, count(10, 2.5))), repr(mixed2))
    c = count(10, 1.0)
    check("int then float", (isinstance(next(c), int), isinstance(next(c), float)), (True, True))


def test_cycle() -> None:
    check("abc", take(10, cycle('abc')), list('abcabcabca'))
    check_empty("empty", list(cycle('')))
    check("gen3", list(islice(cycle(gen3()), 10)), [0, 1, 2, 0, 1, 2, 0, 1, 2, 0])


class ExpectedError(Exception):
    pass


def delayed_raise(n: int = 0) -> Iterator[str]:
    for i in range(n):
        yield 'yo'
    raise ExpectedError


def test_groupby() -> None:
    no_ints: list[int] = []
    check("empty", len(list(groupby(no_ints))), 0)
    check("empty key", len(list(groupby(no_ints, key=lambda x: -x))), 0)

    # Check normal input
    s = [(0, 10, 20), (0, 11, 21), (0, 12, 21), (1, 13, 21), (1, 14, 22),
         (2, 15, 22), (3, 16, 23), (3, 17, 23)]
    dup = []
    for k, g in groupby(s, lambda r: r[0]):
        for elem in g:
            assert k == elem[0]
            dup.append(elem)
    check("dup", s == dup, True)

    # Check nested case
    dup = []
    for k, g in groupby(s, testR):
        for ik, ig in groupby(g, testR2):
            for elem in ig:
                assert k == elem[0]
                assert ik == elem[2]
                dup.append(elem)
    check("nested", s == dup, True)

    # Check case where inner iterator is not used
    keys = [k for k, g in groupby(s, testR)]
    expectedkeys = set([r[0] for r in s])
    check("keys", set(keys), expectedkeys)
    check("len keys", len(keys), len(expectedkeys))

    # Check case where inner iterator is used after advancing the groupby
    # iterator
    s2 = list(zip('AABBBAAAA', range(9)))
    it = groupby(s2, lambda r: r[0])
    _, g1 = next(it)
    _, g2 = next(it)
    _, g3 = next(it)
    check_empty("g1", list(g1))
    check_empty("g2", list(g2))
    check("g3", next(g3), ('A', 5))
    list(it)  # exhaust the groupby iterator
    check_empty("g3 after", list(g3))

    # Exercise pipes and filters style
    s3 = 'abracadabra'
    # sort s | uniq
    r = [k for k, g in groupby(sorted(s3))]
    check("uniq", r, ['a', 'b', 'c', 'd', 'r'])
    # sort s | uniq -d
    r = [k for k, g in groupby(sorted(s3)) if list(islice(g, 1, 2))]
    check("uniq -d", r, ['a', 'b', 'r'])
    # sort s | uniq -c
    rc = [(len(list(g)), k) for k, g in groupby(sorted(s3))]
    check("uniq -c", rc, [(5, 'a'), (2, 'b'), (1, 'c'), (1, 'd'), (2, 'r')])
    # sort s | uniq -c | sort -rn | head -3
    rc = sorted([(len(list(g)), k) for k, g in groupby(sorted(s3))], reverse=True)[:3]
    check("head -3", rc, [(5, 'a'), (2, 'r'), (2, 'b')])

    # iter.__next__ failure on outer object
    try:
        [list(g) for k, g in groupby(delayed_raise(0))]
    except ExpectedError:
        print("ExpectedError outer")
    # iter.__next__ failure on inner object
    try:
        [list(g) for k, g in groupby(delayed_raise(1))]
    except ExpectedError:
        print("ExpectedError inner")

    # keyfunc failure on outer object
    def keyfunc0(obj: int) -> int:
        raise ExpectedError
    try:
        [list(g) for k, g in groupby([0], keyfunc0)]
    except ExpectedError:
        print("ExpectedError keyfunc outer")
    skip = [1]

    def keyfunc1(obj: int) -> int:
        if skip[0] > 0:
            skip[0] -= 1
            return obj
        raise ExpectedError
    try:
        [list(g) for k, g in groupby([0, 0], keyfunc1)]
    except ExpectedError:
        print("ExpectedError keyfunc inner")


def test_filterfalse() -> None:
    check("isEven", list(filterfalse(isEven, range(6))), [1, 3, 5])
    check("None", list(filterfalse(None, [0, 1, 0, 2, 0])), [0, 0, 0])
    check("bool", list(filterfalse(bool, [0, 1, 0, 2, 0])), [0, 0, 0])
    check("count", take(4, filterfalse(isEven, count())), [1, 3, 5, 7])


def test_ziplongest() -> None:
    r6 = list(range(6))
    want1: list[tuple[str | None, int | None]] = [('a', 0), ('b', 1), ('c', 2), (None, 3), (None, 4), (None, 5)]
    check("abc range(6)", list(zip_longest('abc', r6)), want1)
    want2: list[tuple[int | None, str | None]] = [(0, 'a'), (1, 'b'), (2, 'c'), (3, None), (4, None), (5, None)]
    check("range(6) abc", list(zip_longest(r6, 'abc')), want2)
    a = list(range(1000))
    b = list(range(2000, 2100))
    c = list(range(3000, 3050))
    target3 = [(a[i] if i < len(a) else None, b[i] if i < len(b) else None, c[i] if i < len(c) else None) for i in range(1000)]
    check("three", list(zip_longest(a, b, c)) == target3, True)
    target3x = [(a[i] if i < len(a) else -1, b[i] if i < len(b) else -1, c[i] if i < len(c) else -1) for i in range(1000)]
    check("fillvalue", list(zip_longest(a, b, c, **{"fillvalue": -1})) == target3x, True)
    want3: list[tuple[str | None, int | None]] = [('a', 0), ('b', 1), ('c', 2)]
    check("infinite", take(3, zip_longest('abcdef', count())), want3)  # take 3 from infinite input
    check("none", len(list(zip_longest())), 0)
    no_ints: list[int] = []
    check_empty("[]", list(zip_longest(no_ints)))
    want4: list[tuple[str | None]] = [(c,) for c in 'abcdef']
    check("one", list(zip_longest('abcdef')), want4)
    want5: list[tuple[str | None, str | None]] = [('a', 'd'), ('b', 'e'), ('c', 'f'), (None, 'g')]  # list(zip(list('abc') + [None], 'defg'))
    check("defg", list(zip_longest('abc', 'defg', **{})), want5)  # empty keyword dict
    want6: list[tuple[str | None, ...]] = [('a', 'd'), ('b', 'e'), ('c', 'f')]
    check("pairs", [tuple(list(pair)) for pair in zip_longest('abc', 'def')], want6)
    want7: list[tuple[str | None, str | None]] = [('a', 'd'), ('b', 'e'), ('c', 'f')]
    check("pairs 2", [pair for pair in zip_longest('abc', 'def')], want7)


class Repeater:
    # this class is similar to itertools.repeat
    def __init__(self, o: int, t: int, e: bool) -> None:
        self.o = o
        self.t = int(t)
        self.e = e  # (True: RuntimeError, False: StopIteration)

    def __iter__(self):
        return self

    def __next__(self) -> int:
        if self.t > 0:
            self.t -= 1
            return self.o
        elif self.e:
            raise RuntimeError
        else:
            raise StopIteration


def test_bug_7244() -> None:
    # Formerly this code in would fail in debug mode
    # with Undetected Error and Stop Iteration
    r1 = Repeater(1, 3, False)
    r2 = Repeater(2, 4, False)
    result = []
    for i, j in zip_longest(r1, r2, fillvalue=0):
        result.append((i, j))
    check("run", result, [(1, 2), (1, 2), (1, 2), (0, 2)])

    # Formerly, the RuntimeError would be lost
    # and StopIteration would stop as expected
    r3 = Repeater(1, 3, True)
    r4 = Repeater(2, 4, False)
    it = zip_longest(r3, r4, fillvalue=0)
    check("next", next(it), (1, 2))
    check("next", next(it), (1, 2))
    check("next", next(it), (1, 2))
    try:
        next(it)
    except RuntimeError:
        print("RuntimeError")


def test_pairwise() -> None:
    check_empty("''", list(pairwise('')))
    check_empty("a", list(pairwise('a')))
    check("ab", list(pairwise('ab')), [('a', 'b')])
    check("abcde", list(pairwise('abcde')), [('a', 'b'), ('b', 'c'), ('c', 'd'), ('d', 'e')])
    check("10_000", list(pairwise(range(10_000))) == list(zip(range(10_000), range(1, 10_000))), True)


def product1(pools: list[list[int]]):
    n = len(pools)
    if n == 0:
        yield tuple([0 for i in range(0)])
        return
    if any(len(pool) == 0 for pool in pools):
        return
    indices = [0] * n
    yield tuple(pool[i] for pool, i in zip(pools, indices))
    while 1:
        for i in reversed(range(n)):  # right to left
            if indices[i] == len(pools[i]) - 1:
                continue
            indices[i] += 1
            for j in range(i + 1, n):
                indices[j] = 0
            yield tuple(pool[i] for pool, i in zip(pools, indices))
            break
        else:
            return


def product2(pools: list[list[int]], repeat: int = 1):
    'Pure python version used in docs'
    if repeat < 0:
        raise ValueError('repeat argument cannot be negative')
    pools = [list(pool) for pool in pools] * repeat
    result: list[list[int]] = [[]]
    for pool in pools:
        result = [x + [y] for x in result for y in pool]
    for prd in result:
        yield tuple(prd)


def test_product() -> None:
    no_ints: list[int] = []
    check("zero", list(product()), [()])
    check("one", list(product('ab')), [('a',), ('b',)])
    check("two", list(product(range(2), range(3))), [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)])
    check_empty("first empty", list(product(no_ints, range(2), range(3))))
    check_empty("middle empty", list(product(range(2), no_ints, range(3))))
    check_empty("last empty", list(product(range(2), range(3), no_ints)))
    for r in range(4):
        assert list(product(range(2), range(3), repeat=r)) == list(product2([list(range(2)), list(range(3))], r))
        assert list(product(no_ints, range(2), repeat=r)) == list(product2([no_ints, list(range(2))], r))
        assert list(product(range(2), no_ints, repeat=r)) == list(product2([list(range(2)), no_ints], r))
    print("repeat checked")
    check("5**4", len(list(product(range(5), repeat=4))), 5 ** 4)
    random.seed(0)
    argtypes = ['', 'abc', '', 'abcd', 'abcdefg', 'abcdefghijk']
    for i in range(100):
        nargs = random.randrange(5)
        args = [random.choice(argtypes) for j in range(nargs)]
        expected_len = prod([len(a) for a in args])
        pools = [[ord(ch) for ch in a] for a in args]
        got = list(product2(pools))
        assert len(got) == expected_len
        assert got == list(product1(pools))
        if nargs == 2:
            assert list(product(args[0], args[1])) == [(chr(t[0]), chr(t[1])) for t in got]
    print("random products checked")


def test_repeat() -> None:
    check("keywords", list(repeat(object='a', times=3)), ['a', 'a', 'a'])
    check("lzip", list(zip(range(3), repeat('a'))), [(0, 'a'), (1, 'a'), (2, 'a')])
    check("3", list(repeat('a', 3)), ['a', 'a', 'a'])
    check("take", take(3, repeat('a')), ['a', 'a', 'a'])
    check_empty("0", list(repeat('a', 0)))
    check_empty("-3", list(repeat('a', -3)))
    try:
        repeat(None, 'a')
    except TypeError as e:
        print("TypeError", e)
    c = repeat(object='a', times=10)
    check("next", next(c), 'a')


def test_starmap() -> None:
    check("pow", list(starmap(operator.pow, [(x, y) for x, y in zip(range(3), range(1, 7))])), [0 ** 1, 1 ** 2, 2 ** 3])
    check("take", take(3, starmap(operator.pow, ((x, y) for x, y in zip(count(), count(1))))), [0 ** 1, 1 ** 2, 2 ** 3])
    no_pairs: list[tuple[int, int]] = []
    check_empty("empty", list(starmap(operator.pow, no_pairs)))
    try:
        next(starmap(errfunc, [(4,)]))
    except ValueError:
        print("ValueError")


class IntLike:
    def __init__(self, val: int) -> None:
        self.val = val

    def __index__(self) -> int:
        return self.val


def test_islice() -> None:
    hundred = list(range(100))
    check("10, 20, 3", list(islice(hundred, 10, 20, 3)), list(range(10, 20, 3)))
    check("10, 3, 20", list(islice(hundred, 10, 3, 20)), list(range(10, 3, 20)))
    check("10, 20", list(islice(hundred, 10, 20)), list(range(10, 20)))
    check("10, 10", list(islice(hundred, 10, 10)), list(range(10, 10)))
    check("10, 3", list(islice(hundred, 10, 3)), list(range(10, 3)))
    check("20", list(islice(hundred, 20)), list(range(20)))
    # Stop when seqn is exhausted
    check("10, 110, 3", list(islice(hundred, 10, 110, 3)), list(range(10, 100, 3)))
    check("10, 110", list(islice(hundred, 10, 110)), list(range(10, 100)))
    check("110", list(islice(hundred, 110)), list(range(100)))

    # Test stop=None
    ten = list(range(10))
    check("None", list(islice(ten, None)), ten)
    check("None, None", list(islice(ten, None, None)), ten)
    check("None, None, None", list(islice(ten, None, None, None)), ten)
    check("2, None", list(islice(ten, 2, None)), list(range(2, 10)))
    check("1, None, 2", list(islice(ten, 1, None, 2)), list(range(1, 10, 2)))

    # Test number of items consumed     SF #1171417
    it = iter(range(10))
    check("consumed", list(islice(it, 3)), list(range(3)))
    check("rest", list(it), list(range(3, 10)))

    it = iter(range(10))
    check_empty("3, 3", list(islice(it, 3, 3)))
    check("rest", list(it), list(range(3, 10)))

    # Test invalid arguments
    ra = list(range(10))
    try:
        islice(ra)
    except TypeError as e:
        print("TypeError", e)
    try:
        islice(ra, 1, 2, 3, 4)
    except TypeError as e:
        print("TypeError", e)
    try:
        islice(ra, -5, 10, 1)
    except ValueError as e:
        print("ValueError", e)
    try:
        islice(ra, 1, -5, -1)
    except ValueError as e:
        print("ValueError", e)
    try:
        islice(ra, 1, 10, -1)
    except ValueError as e:
        print("ValueError", e)
    try:
        islice(ra, 1, 10, 0)
    except ValueError as e:
        print("ValueError", e)
    try:
        islice(ra, 'a')
    except ValueError as e:
        print("ValueError", e)
    try:
        islice(ra, 'a', 1)
    except ValueError as e:
        print("ValueError", e)
    try:
        islice(ra, 1, 'a')
    except ValueError as e:
        print("ValueError", e)
    try:
        islice(ra, 'a', 1, 1)
    except ValueError as e:
        print("ValueError", e)
    try:
        islice(ra, 1, 'a', 1)
    except ValueError as e:
        print("ValueError", e)
    check("maxsize step", len(list(islice(count(), 1, 10, maxsize))), 1)

    # Issue #10323:  Less islice in a predictable state
    c = count()
    check("predictable", list(islice(c, 1, 3, 50)), [1])
    check("next", next(c), 3)

    # Issue #30537: islice can accept integer-like objects as
    # arguments
    check("IntLike", list(islice(hundred, IntLike(10))), list(range(10)))
    check("IntLike 2", list(islice(hundred, IntLike(10), IntLike(50))), list(range(10, 50)))
    check("IntLike 3", list(islice(hundred, IntLike(10), IntLike(50), IntLike(5))), list(range(10, 50, 5)))


def test_takewhile() -> None:
    data = [1, 3, 5, 20, 2, 4, 6, 8]
    check("underten", list(takewhile(underten, data)), [1, 3, 5])
    no_ints: list[int] = []
    check_empty("empty", list(takewhile(underten, no_ints)))
    try:
        next(takewhile(errfunc, [4]))
    except ValueError:
        print("ValueError")
    t = takewhile(bool, [1, 1, 1, 0, 0, 0])
    check("bool", list(t), [1, 1, 1])
    try:
        next(t)
    except StopIteration:
        print("StopIteration")


def test_dropwhile() -> None:
    data = [1, 3, 5, 20, 2, 4, 6, 8]
    check("underten", list(dropwhile(underten, data)), [20, 2, 4, 6, 8])
    no_ints: list[int] = []
    check_empty("empty", list(dropwhile(underten, no_ints)))
    try:
        next(dropwhile(errfunc, [4]))
    except ValueError:
        print("ValueError")


def test_tee() -> None:
    n = 200

    no_ints: list[int] = []
    a, b = tee(no_ints)  # test empty iterator
    check_empty("a", list(a))
    check_empty("b", list(b))

    a2, b2 = tee(irange(n))  # test 100% interleaved
    check("interleaved", list(zip(a2, b2)) == list(zip(range(n), range(n))), True)

    a3, b3 = tee(irange(n))  # test 0% interleaved
    check("a3", list(a3) == list(range(n)), True)
    check("b3", list(b3) == list(range(n)), True)

    a4, b4 = tee(irange(n))  # test dealloc of leading iterator
    for i in range(100):
        assert next(a4) == i
    check("b4", list(b4) == list(range(n)), True)

    a5, b5 = tee(irange(n))  # test dealloc of trailing iterator
    for i in range(100):
        assert next(a5) == i
    check("a5", list(a5) == list(range(100, n)), True)

    random.seed(1)
    for j in range(5):  # test randomly interleaved
        order = [0] * n + [1] * n
        random.shuffle(order)
        lists: list[list[int]] = [[], []]
        its = tee(irange(n))
        for i in order:
            value = next(its[i])
            lists[i].append(value)
        assert lists[0] == list(range(n))
        assert lists[1] == list(range(n))
    print("randomly interleaved")

    try:
        tee([1, 2], 'x')
    except TypeError as e:
        print("TypeError", e)

    # test long-lagged and multi-way split
    a6, b6, c6 = tee(range(2000), 3)
    for i in range(100):
        assert next(a6) == i
    check("b6", list(b6) == list(range(2000)), True)
    check("c6", [next(c6), next(c6)], list(range(2)))
    check("a6", list(a6) == list(range(100, 2000)), True)
    check("c6 rest", list(c6) == list(range(2, 2000)), True)

    # test values of n
    try:
        tee('abc', 'invalid')
    except TypeError as e:
        print("TypeError", e)
    try:
        tee(no_ints, -1)
    except ValueError as e:
        print("ValueError", e)
    for k in range(5):
        result = tee('abc', k)
        check("len", len(result), k)
        check("lists", [list(x) for x in result], [list('abc')] * k)

    # tee objects are independent (see bug gh-123884)
    a7, b7 = tee('abc')
    c7, d7 = tee(a7)
    e7, f7 = tee(c7)
    check("independent", len({a7, b7, c7, d7, e7, f7}) == 6, True)

    ans = list('abc')
    long_ans = list(range(10000))
    # check copy (__copy__, which copy.copy() calls)
    a8, b8 = tee('abc')
    check("copy a", list(a8.__copy__()), ans)
    check("copy b", list(b8.__copy__()), ans)
    a9, b9 = tee(range(10000))
    check("copy long a", list(a9.__copy__()) == long_ans, True)
    check("copy long b", list(b9.__copy__()) == long_ans, True)

    # check partially consumed copy
    a10, b10 = tee('abc')
    take(2, a10)
    take(1, b10)
    check("partial a", list(a10.__copy__()), ans[2:])
    check("partial b", list(b10.__copy__()), ans[1:])
    check("a", list(a10), ans[2:])
    check("b", list(b10), ans[1:])
    a11, b11 = tee(range(10000))
    take(100, a11)
    take(60, b11)
    check("partial long a", list(a11.__copy__()) == long_ans[100:], True)
    check("partial long b", list(b11.__copy__()) == long_ans[60:], True)
    check("long a", list(a11) == long_ans[100:], True)
    check("long b", list(b11) == long_ans[60:], True)


class Reenter:
    def __init__(self) -> None:
        self.first = True

    def __iter__(self):
        return self

    def __next__(self) -> int:
        first = self.first
        self.first = False
        if first:
            return next(tee_b)
        return 0


tee_a, tee_b = tee(Reenter())


def test_tee_reenter() -> None:
    try:
        next(tee_a)
    except RuntimeError as e:
        print("RuntimeError", e)


def test_StopIteration() -> None:
    no_ints: list[int] = []
    for name in ("chain", "cycle", "groupby"):
        try:
            if name == "chain":
                next(chain(no_ints))
            elif name == "cycle":
                next(cycle(no_ints))
            else:
                next(groupby(no_ints))
        except StopIteration:
            print(name, "StopIteration")
        try:
            if name == "chain":
                next(chain(StopNow()))
            elif name == "cycle":
                next(cycle(StopNow()))
            else:
                next(groupby(StopNow()))
        except StopIteration:
            print(name, "StopIteration StopNow")
    try:
        next(islice(no_ints, None))
    except StopIteration:
        print("islice StopIteration")
    try:
        next(islice(StopNow(), None))
    except StopIteration:
        print("islice StopIteration StopNow")
    p, q = tee(no_ints)
    try:
        next(p)
    except StopIteration:
        print("tee p StopIteration")
    try:
        next(q)
    except StopIteration:
        print("tee q StopIteration")
    p2, q2 = tee(StopNow())
    try:
        next(p2)
    except StopIteration:
        print("tee p StopIteration StopNow")
    try:
        next(q2)
    except StopIteration:
        print("tee q StopIteration StopNow")
    try:
        next(repeat(None, 0))
    except StopIteration:
        print("repeat StopIteration")
    for name in ("filterfalse", "takewhile", "dropwhile"):
        try:
            if name == "filterfalse":
                next(filterfalse(lambda x: x, no_ints))
            elif name == "takewhile":
                next(takewhile(lambda x: x, no_ints))
            else:
                next(dropwhile(lambda x: x, no_ints))
        except StopIteration:
            print(name, "StopIteration")
        try:
            if name == "filterfalse":
                next(filterfalse(lambda x: x, StopNow()))
            elif name == "takewhile":
                next(takewhile(lambda x: x, StopNow()))
            else:
                next(dropwhile(lambda x: x, StopNow()))
        except StopIteration:
            print(name, "StopIteration StopNow")
    no_pairs: list[tuple[int]] = []
    try:
        next(starmap(lambda x: x, no_pairs))
    except StopIteration:
        print("starmap StopIteration")


# --- TestExamples ---

def TestExamples_test_accumulate() -> None:
    check("accumulate", list(accumulate([1, 2, 3, 4, 5])), [1, 3, 6, 10, 15])


def TestExamples_test_chain() -> None:
    check("chain", ''.join(chain('ABC', 'DEF')), 'ABCDEF')


def TestExamples_test_chain_from_iterable() -> None:
    check("from_iterable", ''.join(chain.from_iterable(['ABC', 'DEF'])), 'ABCDEF')


def TestExamples_test_combinations() -> None:
    check("ABCD", list(combinations('ABCD', 2)), strs([('A', 'B'), ('A', 'C'), ('A', 'D'), ('B', 'C'), ('B', 'D'), ('C', 'D')]))
    check("range", list(combinations(range(4), 3)), ints([(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]))


def TestExamples_test_combinations_with_replacement() -> None:
    check("ABC", list(combinations_with_replacement('ABC', 2)), strs([('A', 'A'), ('A', 'B'), ('A', 'C'), ('B', 'B'), ('B', 'C'), ('C', 'C')]))


def TestExamples_test_compress() -> None:
    check("compress", list(compress('ABCDEF', [1, 0, 1, 0, 1, 1])), list('ACEF'))


def TestExamples_test_count() -> None:
    check("count", list(islice(count(10), 5)), [10, 11, 12, 13, 14])


def TestExamples_test_cycle() -> None:
    check("cycle", list(islice(cycle('ABCD'), 12)), list('ABCDABCDABCD'))


def TestExamples_test_dropwhile() -> None:
    check("dropwhile", list(dropwhile(lambda x: x < 5, [1, 4, 6, 4, 1])), [6, 4, 1])


def TestExamples_test_groupby() -> None:
    check("keys", [k for k, g in groupby('AAAABBBCCDAABBB')], list('ABCDAB'))
    check("groups", [(list(g)) for k, g in groupby('AAAABBBCCD')], [list('AAAA'), list('BBB'), list('CC'), list('D')])


def TestExamples_test_filterfalse() -> None:
    check("filterfalse", list(filterfalse(lambda x: x % 2, range(10))), [0, 2, 4, 6, 8])


def TestExamples_test_islice() -> None:
    check("2", list(islice('ABCDEFG', 2)), list('AB'))
    check("2, 4", list(islice('ABCDEFG', 2, 4)), list('CD'))
    check("2, None", list(islice('ABCDEFG', 2, None)), list('CDEFG'))
    check("0, None, 2", list(islice('ABCDEFG', 0, None, 2)), list('ACEG'))


def TestExamples_test_zip_longest() -> None:
    check("zip_longest", list(zip_longest('ABCD', 'xy', fillvalue='-')), [('A', 'x'), ('B', 'y'), ('C', '-'), ('D', '-')])


def TestExamples_test_permutations() -> None:
    check("ABCD", list(permutations('ABCD', 2)), strs([tuple(t) for t in 'AB AC AD BA BC BD CA CB CD DA DB DC'.split()]))
    check("range", list(permutations(range(3))), ints([(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]))


def TestExamples_test_product() -> None:
    check("ABCD xy", list(product('ABCD', 'xy')), [(t[0], t[1]) for t in 'Ax Ay Bx By Cx Cy Dx Dy'.split()])
    check("repeat", list(product(range(2), repeat=3)),
          ints([(0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1), (1, 0, 0), (1, 0, 1), (1, 1, 0), (1, 1, 1)]))


def TestExamples_test_repeat() -> None:
    check("repeat", list(repeat(10, 3)), [10, 10, 10])


def TestExamples_test_stapmap() -> None:
    check("starmap", list(starmap(pow, [(2, 5), (3, 2), (10, 3)])), [32, 9, 1000])


def TestExamples_test_takewhile() -> None:
    check("takewhile", list(takewhile(lambda x: x < 5, [1, 4, 6, 4, 1])), [1, 4])


# --- TestPurePythonRoughEquivalents ---

def batched_recipe(iterable, n: int):
    "Batch data into tuples of length n. The last batch may be shorter."
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch


def TestPurePythonRoughEquivalents_test_batched_recipe() -> None:
    for iterable in ['', 'a', 'ab', 'abc', 'abcd', 'abcde', 'abcdef', 'abcdefg']:
        for n in [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
            e1 = ""
            try:
                r1 = list(batched(iterable, n))
            except ValueError as e:
                e1 = str(e)
                r1 = []
            e2 = ""
            try:
                r2 = list(batched_recipe(iterable, n))
            except ValueError as e:
                e2 = str(e)
                r2 = []
            assert r1 == r2
            assert e1 == e2
    print("batched recipe checked")


# --- TestVariousIteratorArgs ---

def R(seqn):
    'Regular generator'
    for i in seqn:
        yield i


class I:
    'Sequence using iterator protocol'
    def __init__(self, seqn) -> None:
        self.seqn = seqn
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.i >= len(self.seqn):
            raise StopIteration
        v = self.seqn[self.i]
        self.i += 1
        return v


class Ig:
    'Sequence using iterator protocol defined with a generator'
    def __init__(self, seqn) -> None:
        self.seqn = seqn
        self.i = 0

    def __iter__(self):
        for val in self.seqn:
            yield val


class E:
    'Test propagation of exceptions'
    def __init__(self, seqn) -> None:
        self.seqn = seqn
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self) -> int:
        return 3 // 0


class E2:
    'Test propagation of exceptions after two iterations'
    def __init__(self, seqn) -> None:
        self.seqn = seqn
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.i == 2:
            raise ZeroDivisionError
        v = self.seqn[self.i]
        self.i += 1
        return v


class S:
    'Test immediate stop'
    def __init__(self, seqn) -> None:
        pass

    def __iter__(self):
        return self

    def __next__(self) -> int:
        raise StopIteration


def L(seqn):
    'Test multiple tiers of iterators'
    return chain((x for x in R(Ig(seqn))))


def various(s) -> None:
    # TestVariousIteratorArgs' loops over its test values, for one of them
    assert list(chain(I(s))) == list(s) and list(chain(Ig(s))) == list(s) and list(chain(S(s))) == []
    assert list(chain(L(s))) == list(s) and list(chain(R(s))) == list(s)
    assert list(chain(I(s), I(s))) == list(s) + list(s) and list(chain(R(s), L(s))) == list(s) + list(s)
    assert list(compress(I(s), repeat(1))) == list(s) and list(compress(Ig(s), repeat(1))) == list(s)
    assert list(compress(S(s), repeat(1))) == [] and list(compress(L(s), repeat(1))) == list(s)
    assert list(compress(R(s), repeat(1))) == list(s)
    tgtlen = len(s) * 3
    expected = list(s) * 3
    assert list(islice(cycle(I(s)), tgtlen)) == expected and list(islice(cycle(Ig(s)), tgtlen)) == expected
    assert list(islice(cycle(S(s)), tgtlen)) == [] and list(islice(cycle(L(s)), tgtlen)) == expected
    assert list(islice(cycle(R(s)), tgtlen)) == expected
    assert list(zip_longest(I(s))) == list(zip(s)) and list(zip_longest(Ig(s), L(s))) == list(zip(s, s))
    assert list(zip_longest(S(s))) == [] and list(zip_longest(R(s), I(s))) == list(zip(s, s))
    assert list(islice(I(s), 1, None, 2)) == list(s)[1::2] and list(islice(Ig(s), 1, None, 2)) == list(s)[1::2]
    assert list(islice(S(s), 1, None, 2)) == [] and list(islice(L(s), 1, None, 2)) == list(s)[1::2]
    assert list(islice(R(s), 1, None, 2)) == list(s)[1::2]
    seq = list(s)
    assert list(pairwise(I(s))) == list(zip(seq, seq[1:])) and list(pairwise(Ig(s))) == list(zip(seq, seq[1:]))
    assert list(pairwise(S(s))) == [] and list(pairwise(L(s))) == list(zip(seq, seq[1:]))
    assert list(pairwise(R(s))) == list(zip(seq, seq[1:]))
    for it1, it2 in [tee(I(s))]:
        assert list(it1) == seq and list(it2) == seq
    it3, it4 = tee(L(s))
    assert list(it3) == seq and list(it4) == seq
    it5, it6 = tee(S(s))
    assert list(it5) == [] and list(it6) == []
    try:
        list(chain(E(s)))
    except ZeroDivisionError:
        pass
    try:
        list(compress(E(s), repeat(1)))
    except ZeroDivisionError:
        pass
    try:
        list(cycle(E(s)))
    except ZeroDivisionError:
        pass
    try:
        list(zip_longest(E(s)))
    except ZeroDivisionError:
        pass
    try:
        list(islice(E(s), 10))
    except ZeroDivisionError:
        pass
    try:
        list(pairwise(E(s)))
    except ZeroDivisionError:
        pass
    try:
        list(tee(E(s))[0])
    except ZeroDivisionError:
        pass
    try:
        product(E(s))
    except ZeroDivisionError:
        pass


def various_numbers(s: list[int]) -> None:
    # the tests over lists of numbers: accumulate(), batched(), groupby(), filterfalse(),
    # starmap(), takewhile() and dropwhile()
    r = [1, 3, 6, 10, 15]
    assert list(accumulate(I([1, 2, 3, 4, 5]))) == r and list(accumulate(Ig([1, 2, 3, 4, 5]))) == r
    assert list(accumulate(L([1, 2, 3, 4, 5]))) == r and list(accumulate(R([1, 2, 3, 4, 5]))) == r
    assert list(accumulate(S([1, 2, 3, 4, 5]))) == []
    assert [k for k, sb in groupby(I(s))] == s and [k for k, sb in groupby(Ig(s))] == s
    assert [k for k, sb in groupby(S(s))] == [] and [k for k, sb in groupby(L(s))] == s
    assert [k for k, sb in groupby(R(s))] == s
    odd = [x for x in s if isOdd(x)]
    assert list(filterfalse(isEven, I(s))) == odd and list(filterfalse(isEven, Ig(s))) == odd
    assert list(filterfalse(isEven, S(s))) == [] and list(filterfalse(isEven, L(s))) == odd
    assert list(filterfalse(isEven, R(s))) == odd
    tgt = []
    for elem in s:
        if not isEven(elem):
            break
        tgt.append(elem)
    assert list(takewhile(isEven, I(s))) == tgt and list(takewhile(isEven, Ig(s))) == tgt
    assert list(takewhile(isEven, S(s))) == [] and list(takewhile(isEven, L(s))) == tgt
    assert list(takewhile(isEven, R(s))) == tgt
    tgt2 = []
    for elem in s:
        if not tgt2 and isOdd(elem):
            continue
        tgt2.append(elem)
    assert list(dropwhile(isOdd, I(s))) == tgt2 and list(dropwhile(isOdd, Ig(s))) == tgt2
    assert list(dropwhile(isOdd, S(s))) == [] and list(dropwhile(isOdd, L(s))) == tgt2
    assert list(dropwhile(isOdd, R(s))) == tgt2
    for name in ("accumulate", "groupby", "filterfalse", "takewhile", "dropwhile"):
        try:
            if name == "accumulate":
                list(accumulate(E(s)))
            elif name == "groupby":
                list(groupby(E(s)))
            elif name == "filterfalse":
                list(filterfalse(isEven, E(s)))
            elif name == "takewhile":
                list(takewhile(isEven, E(s)))
            else:
                list(dropwhile(isOdd, E(s)))
        except ZeroDivisionError:
            pass
        else:
            assert False, name


def various_starmap(s: list[int]) -> None:
    ss = list(zip(s, s))
    powers = [x ** x for x in s]
    assert list(starmap(operator.pow, I(ss))) == powers and list(starmap(operator.pow, Ig(ss))) == powers
    assert list(starmap(operator.pow, L(ss))) == powers and list(starmap(operator.pow, R(ss))) == powers
    try:
        list(starmap(operator.pow, ((x, x) for x in E(s))))
    except ZeroDivisionError:
        pass


def TestVariousIteratorArgs_tests() -> None:
    various("123")
    various("")
    various(list(range(1000)))
    various(list(range(2000, 2200, 5)))
    no_ints: list[int] = []
    for nums in (list(range(10)), no_ints, list(range(1000)), [7, 11], list(range(2000, 2200, 5))):
        various_numbers(nums)
    for nums in (list(range(10)), no_ints, [7, 11]):
        various_starmap(nums)
    s = 'abcde'
    r: list[tuple[str, ...]] = [('a', 'b'), ('c', 'd'), ('e',)]
    assert list(batched(I(s), 2)) == r and list(batched(Ig(s), 2)) == r and list(batched(L(s), 2)) == r
    assert list(batched(R(s), 2)) == r and list(batched(S(s), 2)) == []
    try:
        list(batched(E(s), 2))
    except ZeroDivisionError:
        print("ZeroDivisionError")
    try:
        list(batched(E2(s), 4))
    except ZeroDivisionError:
        print("ZeroDivisionError")
    print("various iterator arguments checked")


# --- RegressionTests ---

hist: list[int] = []


def gen1() -> Iterator[int]:
    hist.append(0)
    yield 1
    hist.append(1)
    raise AssertionError
    hist.append(2)


def gen2(x: bool) -> Iterator[int]:
    hist.append(3)
    yield 2
    hist.append(4)


def RegressionTests_test_sf_950057() -> None:
    # Make sure that chain() and cycle() catch exceptions immediately
    # rather than when shifting between input sources
    hist.clear()
    try:
        list(chain(gen1(), gen2(False)))
    except AssertionError:
        print("AssertionError")
    check("hist", hist, [0, 1])
    hist.clear()
    try:
        list(chain(gen1(), gen2(True)))
    except AssertionError:
        print("AssertionError")
    check("hist", hist, [0, 1])
    hist.clear()
    try:
        list(cycle(gen1()))
    except AssertionError:
        print("AssertionError")
    check("hist", hist, [0, 1])


def RegressionTests_test_long_chain_of_empty_iterables() -> None:
    # Make sure itertools.chain doesn't run into recursion limits when
    # dealing with long chains of empty iterables. Even with a high
    # number this would probably only fail in Py_DEBUG mode.
    no_ints: list[int] = []
    it = chain.from_iterable(no_ints for unused in range(10000))
    try:
        next(it)
    except StopIteration:
        print("StopIteration")


test_accumulate()
test_batched()
test_chain()
test_chain_from_iterable()
test_combinations()
test_combinations_with_replacement()
test_permutations()
test_combinatorics()
test_compress()
test_count()
test_count_with_step()
test_cycle()
test_groupby()
test_filterfalse()
test_ziplongest()
test_bug_7244()
test_pairwise()
test_product()
test_repeat()
test_starmap()
test_islice()
test_takewhile()
test_dropwhile()
test_tee()
test_tee_reenter()
test_StopIteration()
TestExamples_test_accumulate()
TestExamples_test_chain()
TestExamples_test_chain_from_iterable()
TestExamples_test_combinations()
TestExamples_test_combinations_with_replacement()
TestExamples_test_compress()
TestExamples_test_count()
TestExamples_test_cycle()
TestExamples_test_dropwhile()
TestExamples_test_groupby()
TestExamples_test_filterfalse()
TestExamples_test_islice()
TestExamples_test_zip_longest()
TestExamples_test_permutations()
TestExamples_test_product()
TestExamples_test_repeat()
TestExamples_test_stapmap()
TestExamples_test_takewhile()
TestPurePythonRoughEquivalents_test_batched_recipe()
TestVariousIteratorArgs_tests()
RegressionTests_test_sf_950057()
RegressionTests_test_long_chain_of_empty_iterables()
