# error: upstream_math_prod_positional_start.py:9: error: prod() takes exactly 1 positional argument (2 given)
# CPython 3.13.16 Lib/test/test_math.py, MathTests.test_prod (prod([10, 20], 1): "start is a
# keyword-only argument"), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; Pystachy rejects the call at compile time,
# with CPython's message.
import math
prod = math.prod
prod([10, 20], 1)     # start is a keyword-only argument
