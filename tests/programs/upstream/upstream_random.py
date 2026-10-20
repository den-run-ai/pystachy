# Adapted from CPython 3.13.16 Lib/test/test_random.py, class MersenneTwister_TestBasicOps (gen
# is a random.Random()) with the TestBasicOps tests it runs: test_seedargs, test_saverestore,
# test_shuffle, test_choice, test_sample, test_sample_inputs, test_sample_with_counts,
# test_choices, test_choices_subnormal, test_choices_with_all_zero_weights,
# test_choices_negative_total, test_choices_infinite_total, test_gauss, test_getrandbits,
# test_bug_9025, test_mu_sigma_default_args, test_guaranteed_stable, test_53_bits_per_float,
# test_rangelimits, test_randrange_nonunit_step, test_randrange_errors, test_choices_algorithms
# and test_sample_counts_equivalence; and class TestDistributions: test_constant,
# test_binomialvariate, test_von_mises_range, test_von_mises_large_kappa and
# test_gammavariate_errors; commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b), assertTrue(x) and the
# like print and assert, assertRaises is a try statement that prints the exception; loops over
# many draws assert without printing. A range used as a population is list(range(...)) (a range
# as a value is not supported); empty displays that nothing types are annotated;
# Counter(x=8) (a keyword constructor, rejected: "Counter.__init__() got an unexpected keyword
# argument 'x'") is Counter({'x': 8}); test_binomialvariate's Counter() of a generator expression
# is of a list comprehension; test_choices' bool weights are test_choices_bool_weights, its
# range(4) weights [0, 1, 2, 3]; the zero, negative and infinite totals are one function;
# test_choices_algorithms also prints the first five choices of each seed (deterministic, as
# test_guaranteed_stable's). test_getrandbits stops at 62 bits and its spans at 54.
# EXCLUDED upstream cases:
# - str, bytes, bytearray, tuple, list, dict, object and >64-bit seeds (test_seedargs' 'a',
#   10**20, 1+2j, ...; test_guaranteed_stable's "the quick brown fox", rejected: "expected bool
#   | float | int | None, got str"; test_bug_27706, test_bug_31482, test_seed_no_mutate_bug_44018,
#   test_referenceImplementation, test_strong_reference_implementation, test_long_seed):
#   documented (lib/README.md: int, bool and float seeds; 63-bit getrandbits); also
#   test_bigrand, test_bigrand_ranges, test_randbelow_logic, test_randrange_bug_1590891,
#   getrandbits() above 62 bits and its 100-bit repeatability values, test_randbytes
#   (rejected: "'int' has no method 'to_bytes'"), test_pickling, test_bug_1727780,
#   setstate()/getstate() errors
# - a range as a population (rejected: "range() is only supported in a for loop, after 'in', or
#   as the argument of list(), tuple(), ..."), test_sample_distribution (a dict keyed by
#   tuple[int, ...], rejected: "dict keys must be int or str, objects, or tuples of int, bool, str,
#   str | None and objects, not tuple[int, ...]"), Fraction weights, test_sample_on_dicts,
#   test_sample_on_sets, test_sample_on_seqsets, test_choice_with_numpy, test_autoseed, the
#   TypeErrors of calls that do not fit (compile-time errors here)
# - test_choices_infinite_total's [-float('inf'), 123] (a list[int | float]: rejected inside
#   lib/bisect.py: "comparing closed union values requires narrowing with isinstance() first")
# - TestDistributions' test_zeroinputs, test_avg_std, test_binomialvariate_* and
#   test_gammavariate_alpha_* (they replace g.random or mock it: rejected, "random.Random.random
#   is a method: call it, random(...) (methods are not values)"), test_betavariate_return_zero;
#   SystemRandom_TestBasicOps, TestRawMersenneTwister, TestRandomSubclassing, TestModule,
#   CommandLineTest
import random
from collections import Counter
from math import factorial

# (upstream's gen is random.Random(); seeded here, so that each run draws the same values)
gen = random.Random(12345)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def randomlist(n: int) -> list[float]:
    return [gen.random() for i in range(n)]


def test_seedargs() -> None:
    for arg in [0, 1, -1]:
        gen.seed(arg)
    gen.seed(None)
    gen.seed(False)
    gen.seed(True)
    gen.seed(3.14)
    print("ok")


def test_saverestore() -> None:
    N = 1000
    gen.seed()
    state = gen.getstate()
    randseq = randomlist(N)
    gen.setstate(state)    # should regenerate the same sequence
    check("same", randseq == randomlist(N), True)


def test_shuffle() -> None:
    shuffle = gen.shuffle
    lst: list[int] = []
    shuffle(lst)
    e: list[int] = []
    check("[]", lst, e)
    lst = [37]
    shuffle(lst)
    check("[37]", lst, [37])
    seqs = [list(range(n)) for n in range(10)]
    shuffled_seqs = [list(range(n)) for n in range(10)]
    for shuffled_seq in shuffled_seqs:
        shuffle(shuffled_seq)
    for (seq, shuffled_seq) in zip(seqs, shuffled_seqs):
        check("len", len(seq) == len(shuffled_seq), True)
        check("set", set(seq) == set(shuffled_seq), True)
    lst = list(range(1000))
    shuffled_lst = list(range(1000))
    shuffle(shuffled_lst)
    check("lst != shuffled_lst", lst != shuffled_lst, True)
    shuffle(lst)
    check("lst != shuffled_lst", lst != shuffled_lst, True)


def test_choice() -> None:
    choice = gen.choice
    e: list[int] = []
    try:
        choice(e)
    except IndexError as ex:
        print("IndexError:", ex)
    check("choice([50])", choice([50]), 50)
    check("in", choice([25, 75]) in [25, 75], True)


def test_sample() -> None:
    N = 100
    population = list(range(N))
    for k in range(N+1):
        s = gen.sample(population, k)
        assert len(s) == k
        uniq = set(s)
        assert len(uniq) == k
        assert uniq <= set(population)
    e: list[int] = []
    check("sample([], 0)", gen.sample(e, 0), e)
    try:
        gen.sample(population, N+1)
    except ValueError as ex:
        print("ValueError:", ex)
    try:
        gen.sample(e, -1)
    except ValueError as ex:
        print("ValueError:", ex)


def test_sample_inputs() -> None:
    gen.sample(list(range(20)), 2)
    gen.sample(str('abcdefghijklmnopqrst'), 2)
    gen.sample(tuple('abcdefghijklmnopqrst'), 2)
    print("ok")


def test_sample_with_counts() -> None:
    sample = gen.sample

    # General case
    colors = ['red', 'green', 'blue', 'orange', 'black', 'brown', 'amber']
    counts = [500,      200,     20,       10,       5,       0,       1 ]
    k = 700
    summary = Counter(sample(colors, counts=counts, k=k))
    check("sum", sum(summary.values()), k)
    for color, weight in zip(colors, counts):
        assert summary[color] <= weight
    check("brown", 'brown' in summary, False)

    # Case that exhausts the population
    k = sum(counts)
    summary = Counter(sample(colors, counts=counts, k=k))
    check("sum", sum(summary.values()), k)
    for color, weight in zip(colors, counts):
        assert summary[color] <= weight
    check("brown", 'brown' in summary, False)

    # Case with population size of 1
    summary = Counter(sample(['x'], counts=[10], k=8))
    check("summary", summary, Counter({'x': 8}))

    # Case with all counts equal.
    nc = len(colors)
    summary = Counter(sample(colors, counts=[10]*nc, k=10*nc))
    check("summary", summary == Counter(10*colors), True)

    try:
        sample(['red', 'green', 'blue'], counts=[-3, -7, -8], k=2)      # counts are negative
    except ValueError as e:
        print("ValueError:", e)
    try:
        sample(['red', 'green'], counts=[10, 10], k=21)                 # population too small
    except ValueError as e:
        print("ValueError:", e)
    try:
        sample(['red', 'green', 'blue'], counts=[1, 2], k=2)            # too few counts
    except ValueError as e:
        print("ValueError:", e)
    try:
        sample(['red', 'green', 'blue'], counts=[1, 2, 3, 4], k=2)      # too many counts
    except ValueError as e:
        print("ValueError:", e)
    es: list[str] = []
    ei: list[int] = []
    check("zero counts", sample('abc', k=0, counts=[0, 0, 0]), sample(es, k=0))
    check("empty", sample(es, 0, counts=ei), sample(es, 0))
    try:
        sample(es, 1, counts=ei)
    except ValueError as e:
        print("ValueError:", e)
    try:
        sample('x', 1, counts=[0])
    except ValueError as e:
        print("ValueError:", e)


def test_choices() -> None:
    choices = gen.choices
    data = ['red', 'green', 'blue', 'yellow']
    str_data = 'abcd'

    for sample in [
        choices(data, k=5),
        choices(data, [0, 1, 2, 3], k=5),
        choices(k=5, population=data, weights=[0, 1, 2, 3]),
        choices(k=5, population=data, cum_weights=[0, 1, 2, 3]),
    ]:
        check("len", len(sample), 5)
        check("subset", set(sample) <= set(data), True)

    e: list[str] = []
    check("k=0", choices(data, k=0), e)
    check("k=-1", choices(data, k=-1), e)
    check("str", set(choices(str_data, k=5)) <= set(str_data), True)
    check("None", set(choices(data, None, k=5)) <= set(data), True)
    check("weights=None", set(choices(data, weights=None, k=5)) <= set(data), True)
    try:
        choices(data, [1,2], k=5)
    except ValueError as ex:
        print("ValueError:", ex)
    for w1 in [[15, 10, 25, 30], [1, 0, 1, 0]]:
        check("int weights", set(choices(data, w1, k=5)) <= set(data), True)
    check("float weights", set(choices(data, [15.1, 10.2, 25.2, 30.3], k=5)) <= set(data), True)
    try:
        choices(data, cum_weights=[1,2], k=5)
    except ValueError as ex:
        print("ValueError:", ex)
    try:
        choices(data, [0, 1, 2, 3], cum_weights=[0, 1, 2, 3], k=5)
    except TypeError as ex:
        print("TypeError:", ex)
    check("int cum", set(choices(data, cum_weights=[15, 10, 25, 30], k=5)) <= set(data), True)
    check("float cum", set(choices(data, cum_weights=[15.1, 10.2, 25.2, 30.3], k=5)) <= set(data), True)

    check("a", choices('abcd', [1, 0, 0, 0]), ['a'])
    check("b", choices('abcd', [0, 1, 0, 0]), ['b'])
    check("c", choices('abcd', [0, 0, 1, 0]), ['c'])
    check("d", choices('abcd', [0, 0, 0, 1]), ['d'])

    try:
        choices(e, k=1)
    except IndexError as ex:
        print("IndexError:", ex)
    ew: list[int] = []
    try:
        choices(e, weights=ew, k=1)
    except IndexError as ex:
        print("IndexError:", ex)
    try:
        choices(e, cum_weights=ew, k=5)
    except IndexError as ex:
        print("IndexError:", ex)


def test_choices_bool_weights() -> None:
    data = ['red', 'green', 'blue', 'yellow']
    check("bool weights", set(gen.choices(data, [True, False, True, False], k=5)) <= set(data), True)


def test_choices_subnormal() -> None:
    gen.choices(population=[1, 2], weights=[1e-323, 1e-323], k=5000)
    print("ok")


def test_choices_zero_negative_infinite_total() -> None:
    try:
        gen.choices('AB', [0.0, 0.0])
    except ValueError as e:
        print("ValueError:", e)
    try:
        gen.choices('ABC', [3, -5, 1])
    except ValueError as e:
        print("ValueError:", e)
    for w in [[float('inf')]]:
        try:
            gen.choices('A', w)
        except ValueError as e:
            print("ValueError:", e)
    try:
        gen.choices('AB', [0.0, float('inf')])
    except ValueError as e:
        print("ValueError:", e)
    try:
        gen.choices('AB', [0.0, float('nan')])
    except ValueError as e:
        print("ValueError:", e)
    try:
        gen.choices('AB', [float('-inf'), float('inf')])
    except ValueError as e:
        print("ValueError:", e)


def test_gauss() -> None:
    for seed in 1, 12, 123, 1234, 12345, 123456, 654321:
        gen.seed(seed)
        x1 = gen.random()
        y1 = gen.gauss(0, 1)

        gen.seed(seed)
        x2 = gen.random()
        y2 = gen.gauss(0, 1)

        check("x", x1, x2)
        check("y", y1, y2)


def test_getrandbits() -> None:
    for k in range(1, 63):
        assert 0 <= gen.getrandbits(k) < 2**k
    check("getrandbits(0)", gen.getrandbits(0), 0)

    getbits = gen.getrandbits
    for span in [1, 2, 3, 4, 31, 32, 32, 52, 53, 54]:
        all_bits = 2**span-1
        cum = 0
        cpl_cum = 0
        for i in range(100):
            v = getbits(span)
            cum |= v
            cpl_cum |= all_bits ^ v
        check("cum", cum, all_bits)
        check("cpl_cum", cpl_cum, all_bits)
    try:
        gen.getrandbits(-1)
    except ValueError as e:
        print("ValueError:", e)


def test_bug_9025() -> None:
    n = 100000
    randrange = gen.randrange
    k = sum(randrange(6755399441055744) % 3 == 2 for i in range(n))
    check("ok", 0.30 < k/n < .37, True)


def test_mu_sigma_default_args() -> None:
    check("normalvariate", isinstance(gen.normalvariate(), float), True)
    check("gauss", isinstance(gen.gauss(), float), True)


def test_guaranteed_stable() -> None:
    gen.seed(3456147, version=1)
    check("v1", [gen.random().hex() for i in range(4)],
        ['0x1.ac362300d90d2p-1', '0x1.9d16f74365005p-1',
         '0x1.1ebb4352e4c4dp-1', '0x1.1a7422abf9c11p-1'])


def test_53_bits_per_float() -> None:
    span = 2 ** 53
    cum = 0
    for i in range(100):
        cum |= int(gen.random() * span)
    check("cum", cum, span-1)


def test_rangelimits() -> None:
    for start, stop in [(-2,0), (-(2**60)-2,-(2**60)), (2**60,2**60+2)]:
        check("set", set(range(start,stop)) ==
            set([gen.randrange(start,stop) for i in range(100)]), True)


def test_randrange_nonunit_step() -> None:
    rint = gen.randrange(0, 10, 2)
    check("in", rint in (0, 2, 4, 6, 8), True)
    rint = gen.randrange(0, 2, 2)
    check("rint", rint, 0)


def test_randrange_errors() -> None:
    try:
        gen.randrange(3, 3)
    except ValueError as e:
        print("ValueError:", e)
    try:
        gen.randrange(-721)
    except ValueError as e:
        print("ValueError:", e)
    try:
        gen.randrange(0, 100, -12)
    except ValueError as e:
        print("ValueError:", e)
    try:
        gen.randrange(0, 42, 0)
    except ValueError as e:
        print("ValueError:", e)


def test_choices_algorithms() -> None:
    choices = gen.choices
    n = 104729

    gen.seed(8675309)
    a = gen.choices(list(range(n)), k=10000)

    gen.seed(8675309)
    b = gen.choices(list(range(n)), [1]*n, k=10000)
    check("a == b", a == b, True)

    gen.seed(8675309)
    c = gen.choices(list(range(n)), cum_weights=list(range(1, n+1)), k=10000)
    check("a == c", a == c, True)

    # American Roulette
    population = ['Red', 'Black', 'Green']
    weights = [18, 18, 2]
    cum_weights = [18, 36, 38]
    expanded_population = ['Red'] * 18 + ['Black'] * 18 + ['Green'] * 2

    gen.seed(9035768)
    a2 = gen.choices(expanded_population, k=10000)

    gen.seed(9035768)
    b2 = gen.choices(population, weights, k=10000)
    check("a == b", a2 == b2, True)

    gen.seed(9035768)
    c2 = gen.choices(population, cum_weights=cum_weights, k=10000)
    check("a == c", a2 == c2, True)
    print(a[:5], a2[:5])


def test_sample_counts_equivalence() -> None:
    sample = gen.sample
    seed = gen.seed

    colors =  ['red', 'green', 'blue', 'orange', 'black', 'amber']
    counts = [500,      200,     20,       10,       5,       1 ]
    k = 700
    seed(8675309)
    s1 = sample(colors, counts=counts, k=k)
    seed(8675309)
    expanded = [color for (color, count) in zip(colors, counts) for i in range(count)]
    check("len", len(expanded), sum(counts))
    s2 = sample(expanded, k=k)
    check("s1 == s2", s1 == s2, True)

    pop = 'abcdefghi'
    counts = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    seed(8675309)
    s3 = ''.join(sample(pop, counts=counts, k=30))
    expanded2 = ''.join([letter for (letter, count) in zip(pop, counts) for i in range(count)])
    seed(8675309)
    s4 = ''.join(sample(expanded2, k=30))
    check("s1", s3, s4)


def test_constant() -> None:
    g = random.Random()
    N = 100
    for i in range(N):
        assert g.uniform(10.0, 10.0) == 10.0
        assert g.triangular(10.0, 10.0) == 10.0
        assert g.triangular(10.0, 10.0, 10.0) == 10.0
        assert g.expovariate(float('inf')) == 0.0
        assert g.vonmisesvariate(3.0, float('inf')) == 3.0
        assert g.gauss(10.0, 0.0) == 10.0
        assert g.lognormvariate(0.0, 0.0) == 1.0
        assert g.lognormvariate(-float('inf'), 0.0) == 0.0
        assert g.normalvariate(10.0, 0.0) == 10.0
        assert g.binomialvariate(0, 0.5) == 0
        assert g.binomialvariate(10, 0.0) == 0
        assert g.binomialvariate(10, 1.0) == 10
        assert g.paretovariate(float('inf')) == 1.0
        assert g.weibullvariate(10.0, float('inf')) == 10.0
        assert g.weibullvariate(0.0, 10.0) == 0.0
    print("ok")


def test_binomialvariate() -> None:
    B = random.binomialvariate

    try:
        B(n=-1)
    except ValueError as e:
        print("ValueError:", e)
    try:
        B(n=1, p=-0.5)
    except ValueError as e:
        print("ValueError:", e)
    try:
        B(n=1, p=1.5)
    except ValueError as e:
        print("ValueError:", e)
    check("B(0, 0.5)", B(0, 0.5), 0)
    check("B(10, 0.0)", B(10, 0.0), 0)
    check("B(10, 1.0)", B(10, 1.0), 10)
    check("B(1, 0.3)", B(1, 0.3) in {0, 1}, True)
    check("B(1, 0.9)", B(1, 0.9) in {0, 1}, True)
    check("B(1, 0.0)", B(1, 0.0) in {0}, True)
    check("B(1, 1.0)", B(1, 1.0) in {1}, True)
    check("B(5, 1e-18)", B(5, 1e-18), 0)
    check("B(5, 0.25)", B(5, 0.25) in set(range(6)), True)
    check("B(5, 0.75)", B(5, 0.75) in set(range(6)), True)
    check("B(100, 0.25)", B(100, 0.25) in set(range(101)), True)
    check("B(100, 0.75)", B(100, 0.75) in set(range(101)), True)

    c = Counter([B(4, 0.25) for i in range(100_000)])
    check("c[0]", 29_641 <= c[0] <= 33_641, True)
    check("c[1]", 40_188 <= c[1] <= 44_188, True)
    check("c[2]", 19_094 <= c[2] <= 23_094, True)
    check("c[3]", 2_688  <= c[3] <= 6_688, True)
    check("set(c)", set(c), {0, 1, 2, 3, 4})

    c = Counter([B(100, 0.25) for i in range(100_000)])
    check("sum", 34_214 <= c[20]+c[21]+c[22]+c[23]+c[24] <= 38_214, True)
    check("set(c)", set(c) <= set(range(101)), True)
    check("total", c.total(), 100_000)

    check("huge 0.2", 19_000_000 <= B(100_000_000, 0.2) <= 21_000_000, True)
    check("huge 0.9", 89_000_000 <= B(100_000_000, 0.9) <= 91_000_000, True)


def test_von_mises_range() -> None:
    g = random.Random()
    N = 100
    for mu in 0.0, 0.1, 3.1, 6.2:
        for kappa in 0.0, 2.3, 500.0:
            for _ in range(N):
                sample = g.vonmisesvariate(mu, kappa)
                assert 0 <= sample <= random.TWOPI, (mu, kappa, sample)
    print("ok")


def test_von_mises_large_kappa() -> None:
    random.vonmisesvariate(0, 1e15)
    random.vonmisesvariate(0, 1e100)
    print("ok")


def test_gammavariate_errors() -> None:
    for a, b in [(-1, 3), (0, 2), (2, 0), (1, -3)]:
        try:
            random.gammavariate(a, b)
        except ValueError as e:
            print("ValueError:", e)


test_seedargs()
test_saverestore()
test_shuffle()
test_choice()
test_sample()
test_sample_inputs()
test_sample_with_counts()
test_choices()
test_choices_bool_weights()
test_choices_subnormal()
test_choices_zero_negative_infinite_total()
test_gauss()
test_getrandbits()
test_bug_9025()
test_mu_sigma_default_args()
test_guaranteed_stable()
test_53_bits_per_float()
test_rangelimits()
test_randrange_nonunit_step()
test_randrange_errors()
test_choices_algorithms()
test_sample_counts_equivalence()
test_constant()
test_binomialvariate()
test_von_mises_range()
test_von_mises_large_kappa()
test_gammavariate_errors()
