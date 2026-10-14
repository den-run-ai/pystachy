# Adapted from CPython 3.13.16 Lib/test/test_functools.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. Source SHA-256:
# ec00d729ddde2de6412237b3f8f4196bc0777ce9d0bf99fd69071fb44ce72fd5.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Seven complete upstream methods retain every input and substantive assertion.
# unittest scaffolding becomes annotated functions and plain assertions. Recursive
# decorated helpers move to module scope; their one nonlocal flag uses a one-cell
# list because nested decorated self-recursion is unsupported. No inputs or
# assertions change. CPython's native functools records the oracle, while JIT/AOT
# execute lib/functools.py.
# test_lru_bug_36650 requires a None-only cached return, currently unsupported.
# Other upstream methods are not claimed: object/float/mixed-type keys, runtime
# argument expansion, thread safety, method descriptors, reflection, exception
# chaining, and wrapper metadata are outside this selection's supported surface.
from functools import cache, lru_cache, _CacheInfo


# test_functools.TestCache.test_cache
@cache
def test_cache_fib(n: int) -> int:
    if n < 2:
        return n
    return test_cache_fib(n - 1) + test_cache_fib(n - 2)


def test_cache() -> None:
    assert [test_cache_fib(n) for n in range(16)] == [
        0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
    assert test_cache_fib.cache_info() == _CacheInfo(hits=28, misses=16, maxsize=None, currsize=16)
    test_cache_fib.cache_clear()
    assert test_cache_fib.cache_info() == _CacheInfo(hits=0, misses=0, maxsize=None, currsize=0)
    print('TestCache.test_cache')


# test_functools.TestLRU.test_lru_no_args
def test_lru_no_args() -> None:
    @lru_cache
    def square(x: int) -> int:
        return x ** 2

    assert list(map(square, [10, 20, 10])) == [100, 400, 100]
    assert square.cache_info().hits == 1
    assert square.cache_info().misses == 2
    assert square.cache_info().maxsize == 128
    assert square.cache_info().currsize == 2
    print('TestLRU.test_lru_no_args')


# test_functools.TestLRU.test_lru_bug_35780
once = [True]


@lru_cache(maxsize=10)
def test_lru_bug_35780_f(x: int) -> str:
    rv = f'.{x}.'
    if x == 20 and once[0]:
        once[0] = False
        rv = test_lru_bug_35780_f(x)
    return rv


def test_lru_bug_35780() -> None:
    for x in range(15):
        assert test_lru_bug_35780_f(x) == f'.{x}.'
    assert test_lru_bug_35780_f.cache_info().currsize == 10
    assert test_lru_bug_35780_f(20) == '.20.'
    assert test_lru_bug_35780_f.cache_info().currsize == 10
    print('TestLRU.test_lru_bug_35780')


# test_functools.TestLRU.test_lru_with_maxsize_none
@lru_cache(maxsize=None)
def test_lru_with_maxsize_none_fib(n: int) -> int:
    if n < 2:
        return n
    return test_lru_with_maxsize_none_fib(n - 1) + test_lru_with_maxsize_none_fib(n - 2)


def test_lru_with_maxsize_none() -> None:
    assert [test_lru_with_maxsize_none_fib(n) for n in range(16)] == [
        0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
    assert test_lru_with_maxsize_none_fib.cache_info() == _CacheInfo(hits=28, misses=16, maxsize=None, currsize=16)
    test_lru_with_maxsize_none_fib.cache_clear()
    assert test_lru_with_maxsize_none_fib.cache_info() == _CacheInfo(hits=0, misses=0, maxsize=None, currsize=0)
    print('TestLRU.test_lru_with_maxsize_none')


# test_functools.TestLRU.test_lru_with_maxsize_negative
def test_lru_with_maxsize_negative() -> None:
    @lru_cache(maxsize=-10)
    def eq(n: int) -> int:
        return n

    for i in (0, 1):
        assert [eq(n) for n in range(150)] == list(range(150))
    assert eq.cache_info() == _CacheInfo(hits=0, misses=300, maxsize=0, currsize=0)
    print('TestLRU.test_lru_with_maxsize_negative')


# test_functools.TestLRU.test_lru_with_keyword_args
@lru_cache()
def test_lru_with_keyword_args_fib(n: int) -> int:
    if n < 2:
        return n
    return test_lru_with_keyword_args_fib(n=n - 1) + test_lru_with_keyword_args_fib(n=n - 2)


def test_lru_with_keyword_args() -> None:
    assert [test_lru_with_keyword_args_fib(n=number) for number in range(16)] == [
        0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
    assert test_lru_with_keyword_args_fib.cache_info() == _CacheInfo(hits=28, misses=16, maxsize=128, currsize=16)
    test_lru_with_keyword_args_fib.cache_clear()
    assert test_lru_with_keyword_args_fib.cache_info() == _CacheInfo(hits=0, misses=0, maxsize=128, currsize=0)
    print('TestLRU.test_lru_with_keyword_args')


# test_functools.TestLRU.test_lru_with_keyword_args_maxsize_none
@lru_cache(maxsize=None)
def test_lru_with_keyword_args_maxsize_none_fib(n: int) -> int:
    if n < 2:
        return n
    return test_lru_with_keyword_args_maxsize_none_fib(n=n - 1) + test_lru_with_keyword_args_maxsize_none_fib(n=n - 2)


def test_lru_with_keyword_args_maxsize_none() -> None:
    assert [test_lru_with_keyword_args_maxsize_none_fib(n=number) for number in range(16)] == [
        0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
    assert test_lru_with_keyword_args_maxsize_none_fib.cache_info() == _CacheInfo(hits=28, misses=16, maxsize=None, currsize=16)
    test_lru_with_keyword_args_maxsize_none_fib.cache_clear()
    assert test_lru_with_keyword_args_maxsize_none_fib.cache_info() == _CacheInfo(hits=0, misses=0, maxsize=None, currsize=0)
    print('TestLRU.test_lru_with_keyword_args_maxsize_none')


test_cache()
test_lru_no_args()
test_lru_bug_35780()
test_lru_with_maxsize_none()
test_lru_with_maxsize_negative()
test_lru_with_keyword_args()
test_lru_with_keyword_args_maxsize_none()
