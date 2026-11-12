# Adapted from CPython 3.13.16 Lib/test/test_importlib/test_util.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. Source SHA-256:
# 0e3cda547e2e3383635cb55b69f2d4496d12f98f45fcf00d953bd3579515bfbf.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# unittest scaffolding becomes annotated functions and plain assertions. CPython's own
# importlib.util records the oracle, while JIT/AOT execute lib/importlib/util.py.
# Complete: every method of ResolveNameTests, with each input and assertion (upstream runs the
# class for the frozen and the source importlib; here it runs once). assertRaises becomes
# try/except with a flag.
# Not claimed: the other classes of the file (DecodeSourceBytesTests, ModuleFromSpecTests,
# FindSpecTests, MagicNumberTests, PEP3147Tests, IncompatibleExtensionModuleRestrictionsTests
# and MiscTests), whose functions find, load, decode or cache modules at run time.
from importlib import util


# ResolveNameTests.test_absolute
def test_absolute() -> None:
    # bacon
    assert 'bacon' == util.resolve_name('bacon', None)


# ResolveNameTests.test_absolute_within_package
def test_absolute_within_package() -> None:
    # bacon in spam
    assert 'bacon' == util.resolve_name('bacon', 'spam')


# ResolveNameTests.test_no_package
def test_no_package() -> None:
    # .bacon in ''
    raised = False
    try:
        util.resolve_name('.bacon', '')
    except ImportError:
        raised = True
    assert raised


# ResolveNameTests.test_in_package
def test_in_package() -> None:
    # .bacon in spam
    assert 'spam.eggs.bacon' == util.resolve_name('.bacon', 'spam.eggs')


# ResolveNameTests.test_other_package
def test_other_package() -> None:
    # ..bacon in spam.bacon
    assert 'spam.bacon' == util.resolve_name('..bacon', 'spam.eggs')


# ResolveNameTests.test_escape
def test_escape() -> None:
    # ..bacon in spam
    raised = False
    try:
        util.resolve_name('..bacon', 'spam')
    except ImportError:
        raised = True
    assert raised


test_absolute()
test_absolute_within_package()
test_no_package()
test_in_package()
test_other_package()
test_escape()
print("upstream importlib.util: 6 methods ok")
