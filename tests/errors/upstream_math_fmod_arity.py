# error: unsupported call math.fmod()
# CPython MathTests.testFmod's no-argument TypeError is a compile-time rejection here.
# Source: Lib/test/test_math.py at cbc944f4bc59639a444dd971c737788ba2283a91
# (CPython 3.13.16); PSF License v2, see tests/upstream/CPYTHON-LICENSE.txt
# and THIRD_PARTY_NOTICES.
import math

math.fmod()
