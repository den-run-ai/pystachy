# error: upstream_exceptions_importerror_kw_only.py:8: error: ImportError() got an unexpected keyword argument 'invalid'
# CPython 3.13.16 Lib/test/test_exceptions.py, ImportErrorTests.test_attributes
# (ImportError(invalid='keyword')),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the call runs; Pystachy rejects the call at compile
# time, with CPython's message.
ImportError(invalid='keyword')
