# error: upstream_listcomps_nameerror.py:10: error: name 'x' is not defined
# CPython 3.13.16 Lib/test/test_listcomps.py, ListComprehensionTest.test_nameerror (a
# comprehension's variable read after it, `[x for x in [1]]; x`, in a function),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this NameError where the name is read; Pystachy rejects the read at compile
# time, with CPython's message.
def f() -> None:
    [x for x in [1]]
    x


f()
