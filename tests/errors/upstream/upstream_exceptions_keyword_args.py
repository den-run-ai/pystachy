# error: upstream_exceptions_keyword_args.py:8: error: BaseException() takes no keyword arguments
# CPython 3.13.16 Lib/test/test_exceptions.py, ExceptionTests.testKeywordArgs
# (assertRaises(TypeError, BaseException, a=1)),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; Pystachy rejects the call at compile
# time, with CPython's message.
BaseException(a=1)
