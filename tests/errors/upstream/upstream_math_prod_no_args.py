# error: upstream_math_prod_no_args.py:9: error: prod() takes exactly 1 positional argument (0 given)
# CPython 3.13.16 Lib/test/test_math.py, MathTests.test_prod (assertRaises(TypeError, prod)),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; Pystachy rejects the call at compile time,
# with CPython's message.
import math
prod = math.prod
prod()
