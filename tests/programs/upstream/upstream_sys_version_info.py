# Adapted from CPython 3.13.16 Lib/test/test_sys.py, class SysModuleTest: test_attributes' part
# that checks sys.version_info, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# sys.version_info is a tuple whose attributes are read as sys.version_info.major and the like
# (#480, documented): where upstream reads vi.major of `vi = sys.version_info`, here it is
# sys.version_info.major (vi.major is rejected: "type tuple[int,int,int,str,int] has no
# attribute 'major'"). assertEqual(a, b), assertTrue(x) and assertIn(a, b) print and assert,
# assertIsInstance(x, t) is eq(isinstance(x, t), True).
# EXCLUDED upstream cases:
# - test_attributes' other attributes of sys (sys.float_repr_style is rejected: "unsupported
#   module attribute sys.float_repr_style", and sys.hash_info, sys.int_info, ... likewise),
#   test_sys_version_info_no_instantiation (type() of it)
# - collections.abc (#480): isinstance() of an ABC (Lib/test/test_collections.py's
#   TestOneTrickPonyABCs: isinstance(x, Sized) & co) is rejected: "isinstance() is only
#   supported with the builtin types and classes as its second argument"
import sys


def eq(got, expected) -> None:
    print(repr(got))
    assert got == expected, (got, expected)


def test_attributes_version_info() -> None:
    vi = sys.version_info
    eq(isinstance(vi[:], tuple), True)
    eq(len(vi), 5)
    eq(isinstance(vi[0], int), True)
    eq(isinstance(vi[1], int), True)
    eq(isinstance(vi[2], int), True)
    eq(vi[3] in ("alpha", "beta", "candidate", "final"), True)
    eq(isinstance(vi[4], int), True)
    eq(isinstance(sys.version_info.major, int), True)
    eq(isinstance(sys.version_info.minor, int), True)
    eq(isinstance(sys.version_info.micro, int), True)
    eq(sys.version_info.releaselevel in ("alpha", "beta", "candidate", "final"), True)
    eq(isinstance(sys.version_info.serial, int), True)
    eq(vi[0], sys.version_info.major)
    eq(vi[1], sys.version_info.minor)
    eq(vi[2], sys.version_info.micro)
    eq(vi[3], sys.version_info.releaselevel)
    eq(vi[4], sys.version_info.serial)
    eq(vi > (1,0,0), True)


test_attributes_version_info()
