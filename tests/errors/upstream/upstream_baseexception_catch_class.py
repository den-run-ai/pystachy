# error: upstream_baseexception_catch_class.py:15: error: catching classes that do not inherit from BaseException is not allowed
# CPython 3.13.16 Lib/test/test_baseexception.py, UsageTests.test_catch_non_BaseException
# (its catch_fails(NonBaseException), the except clause of the class),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError when the raised exception reaches the clause, which
# catch_fails catches; Pystachy rejects the clause at compile time, with CPython's message.
class NonBaseException(object):
    pass


try:
    try:
        raise Exception
    except NonBaseException:
        pass
except TypeError:
    pass
