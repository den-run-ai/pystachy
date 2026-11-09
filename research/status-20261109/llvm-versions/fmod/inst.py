# Adapted from CPython 3.13.16 Lib/test/test_math.py, MathTests.testFmod,
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# unittest scaffolding becomes assertions;
# the no-argument case is tests/errors/upstream/upstream_math_fmod_arity.py (a static error).
import math

INF = float("inf")
NINF = -INF
NAN = float("nan")

def equal_result(got: float, expected: float) -> None:
    # ftest also checks zero's sign; these small exact remainders need no ULP tolerance.
    if not (got == expected):
        print('assert failed at line 14')
    if not (math.copysign(1.0, got) == math.copysign(1.0, expected)):
        print('assert failed at line 15')

equal_result(math.fmod(10, 1), 0.0)
equal_result(math.fmod(10, 0.5), 0.0)
equal_result(math.fmod(10, 1.5), 1.0)
equal_result(math.fmod(-10, 1), -0.0)
equal_result(math.fmod(-10, 0.5), -0.0)
equal_result(math.fmod(-10, 1.5), -1.0)
if not (math.isnan(math.fmod(NAN, 1.0))):
    print('assert failed at line 23')
if not (math.isnan(math.fmod(1.0, NAN))):
    print('assert failed at line 24')
if not (math.isnan(math.fmod(NAN, NAN))):
    print('assert failed at line 25')
try:
    math.fmod(1.0, 0.0)
except ValueError:
    pass
else:
    assert False, "expected ValueError"
try:
    math.fmod(INF, 1.0)
except ValueError:
    pass
else:
    assert False, "expected ValueError"
try:
    math.fmod(NINF, 1.0)
except ValueError:
    pass
else:
    assert False, "expected ValueError"
try:
    math.fmod(INF, 0.0)
except ValueError:
    pass
else:
    assert False, "expected ValueError"
if not (math.fmod(3.0, INF) == 3.0):
    print('assert failed at line 50')
if not (math.fmod(-3.0, INF) == -3.0):
    print('assert failed at line 51')
if not (math.fmod(3.0, NINF) == 3.0):
    print('assert failed at line 52')
if not (math.fmod(-3.0, NINF) == -3.0):
    print('assert failed at line 53')
if not (math.fmod(0.0, 3.0) == 0.0):
    print('assert failed at line 54')
if not (math.fmod(0.0, NINF) == 0.0):
    print('assert failed at line 55')
try:
    math.fmod(INF, INF)
except ValueError:
    pass
else:
    assert False, "expected ValueError"
print("CPython MathTests.testFmod: passed")
