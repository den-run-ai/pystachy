# Adapted from CPython 3.13.16 Lib/test/test_setcomps.py, its doctests (`doctests`), commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# The doctests print what each `>>>` line shows; doctests_srange are the srange()/lrange()
# sections.
# EXCLUDED upstream cases:
# - `{None for i in range(10)}` (rejected: "set elements must be int or str, objects, or tuples
#   of int, bool, str, str | None and objects, not None")
# - the scoping sections, at module and function scope: sets of lambdas (rejected: "set
#   elements must be ... not <function <lambda> ...>"; CPython hashes functions by identity)
# - the generator section (grange), the lvalue SyntaxError sections (the same errors at compile
#   time, checked with tools/syntax_sweep.py) and SetComprehensionTest.test_exception_locations
#   (tracebacks)
def doctests() -> None:
    print(sum({i*i for i in range(100) if i&1 == 1}))
    print({2*y + x + 1 for x in (0,) for y in (1,)})
    print(list(sorted({(i,j) for i in range(3) for j in range(4)})))
    print(list(sorted({(i,j) for i in range(4) for j in range(i)})))
    print(sorted({j*j for i in range(4) for j in [i+1]}))
    print(sorted({j*k for i in range(4) for j in [i+1] for k in [j+1]}))
    print(sorted({j*k for i in range(4) for j, k in [(i+1, i+2)]}))
    print(sorted({i*i for i in [*range(4)]}))
    print(sorted({i*i for i in (*range(4),)}))
    i = 20
    print(sum({i*i for i in range(100)}))
    print(i)


def srange(n: int) -> set[int]:
    return {i for i in range(n)}


def doctests_srange() -> None:
    print(list(sorted(srange(10))))
    lrange = lambda n:  {i for i in range(n)}
    print(list(sorted(lrange(10))))


doctests()
doctests_srange()
