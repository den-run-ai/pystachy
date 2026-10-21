# Adapted from CPython 3.13.16 Lib/test/test_builtin.py, class BuiltinTest: test_abs,
# test_callable, test_chr, test_divmod, test_hash, test_hex, test_oct, test_bin (in
# test_hex_oct_bin), test_isinstance, test_len, test_next, test_ord and test_pow, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b), assertTrue(x) and
# assertAlmostEqual(a, b) print and assert, assertRaises is a try statement that prints the
# exception. The classes of the methods are module classes, with annotated special methods
# (AbsClass.__abs__ -> int, ...); test_callable's C1 has only its method; test_chr's ValueErrors
# loop over the arguments; test_divmod's assertAlmostEqual is round(a - b, 7) == 0; test_bin's
# 2**65 is 2**62 (a 64-bit int); test_pow's pow(x, y, z) is its int case, written out.
# EXCLUDED upstream cases:
# - test_abs' abs(-sys.maxsize-1) and test_len's HugeLen and HugeNegativeLen (64-bit ints:
#   OverflowError, documented), test_divmod's (-sys.maxsize-1, -1)
# - classes as values (rejected: "class 'C1' cannot be used as a value (classes are not values:
#   call it, or read an attribute, C.x)"): callable(C1), test_issubclass; callable(__builtins__),
#   c.__call__ assignments, test_hash's hash(f) of a function (rejected: "hash() of <function
#   ...> is not supported"), class X with a 2**100 hash and Z(int)
# - test_ord's ord() of bytes (rejected: "unsupported call ord(bytes)"): ord(b' ') & co; chr(0xff)
#   and ord(chr(sys.maxunicode)) (chr() of a byte value is that byte, documented;
#   "unsupported module attribute sys.maxunicode"); test_pow's complex results, its float pow()
#   with a modulus (rejected: "unsupported call pow(float,int,int)"), keyword arguments to
#   pow() (rejected: "keyword argument 'exp' of pow() is not supported") and so the partial()s
# - the TypeErrors of calls that do not fit (abs('a'), abs(), chr(65.0), hex({}), len of
#   InvalidLen and FloatLen, ...): compile-time errors here; test_next's generator;
#   test_isinstance's isinstance(E, 'foo'), test_len's NoLenMethod
import sys


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


class AbsClass(object):
    def __abs__(self) -> int:
        return -5


def test_abs() -> None:
    check("abs(0)", abs(0), 0)
    check("abs(1234)", abs(1234), 1234)
    check("abs(-1234)", abs(-1234), 1234)
    check("abs(-maxsize)", abs(-sys.maxsize) > 0, True)
    check("abs(0.0)", abs(0.0), 0.0)
    check("abs(3.14)", abs(3.14), 3.14)
    check("abs(-3.14)", abs(-3.14), 3.14)
    check("abs(True)", abs(True), 1)
    check("abs(False)", abs(False), 0)
    check("abs(AbsClass())", abs(AbsClass()), -5)


def f(): pass


class C1:
    def meth(self): pass


class C2(object):
    def __call__(self): pass


class C3(C2): pass


def test_callable() -> None:
    check("len", callable(len), True)
    check("'a'", callable("a"), False)
    check("callable", callable(callable), True)
    check("lambda", callable(lambda x, y: x + y), True)
    check("f", callable(f), True)
    c = C1()
    check("c.meth", callable(c.meth), True)
    check("c", callable(c), False)
    c2 = C2()
    check("c2", callable(c2), True)
    c3 = C3()
    check("c3", callable(c3), True)


def test_chr() -> None:
    check("chr(0)", chr(0), '\0')
    check("chr(32)", chr(32), ' ')
    check("chr(65)", chr(65), 'A')
    check("chr(97)", chr(97), 'a')
    check("0xFFFF", chr(0x0000FFFF), "\U0000FFFF")
    check("0x10000", chr(0x00010000), "\U00010000")
    check("0x10001", chr(0x00010001), "\U00010001")
    check("0xFFFFE", chr(0x000FFFFE), "\U000FFFFE")
    check("0xFFFFF", chr(0x000FFFFF), "\U000FFFFF")
    check("0x100000", chr(0x00100000), "\U00100000")
    check("0x100001", chr(0x00100001), "\U00100001")
    check("0x10FFFE", chr(0x0010FFFE), "\U0010FFFE")
    check("0x10FFFF", chr(0x0010FFFF), "\U0010FFFF")
    for i in [-1, 0x00110000, 1<<24, 2**32-1, -2**32]:
        try:
            chr(i)
        except ValueError as e:
            print("ValueError:", e)


def test_divmod() -> None:
    check("divmod(12, 7)", divmod(12, 7), (1, 5))
    check("divmod(-12, 7)", divmod(-12, 7), (-2, 2))
    check("divmod(12, -7)", divmod(12, -7), (-2, -2))
    check("divmod(-12, -7)", divmod(-12, -7), (1, -5))
    for num, denom, exp_result in [ (3.25, 1.0, (3.0, 0.25)),
                                    (-3.25, 1.0, (-4.0, 0.75)),
                                    (3.25, -1.0, (-4.0, -0.75)),
                                    (-3.25, -1.0, (3.0, -0.25))]:
        result = divmod(num, denom)
        check("q", round(result[0] - exp_result[0], 7) == 0, True)
        check("r", round(result[1] - exp_result[1], 7) == 0, True)


def test_hash() -> None:
    hash(None)
    check("hash(1)", hash(1) == hash(1), True)
    check("hash(1.0)", hash(1) == hash(1.0), True)
    hash('spam')
    check("hash(b'spam')", hash('spam') == hash(b'spam'), True)
    hash((0,1,2,3))
    print("ok")


def test_hex_oct_bin() -> None:
    check("hex(16)", hex(16), '0x10')
    check("hex(-16)", hex(-16), '-0x10')
    check("oct(100)", oct(100), '0o144')
    check("oct(-100)", oct(-100), '-0o144')
    check("bin(0)", bin(0), '0b0')
    check("bin(1)", bin(1), '0b1')
    check("bin(-1)", bin(-1), '-0b1')
    check("bin(2**65)", bin(2**62), '0b1' + '0' * 62)
    check("bin(2**65-1)", bin(2**62-1), '0b' + '1' * 62)
    check("bin(-(2**65))", bin(-(2**62)), '-0b1' + '0' * 62)
    check("bin(-(2**65-1))", bin(-(2**62-1)), '-0b' + '1' * 62)


class C:
    pass


class D(C):
    pass


class E:
    pass


def test_isinstance() -> None:
    c = C()
    d = D()
    e = E()
    check("c C", isinstance(c, C), True)
    check("d C", isinstance(d, C), True)
    check("e C", not isinstance(e, C), True)
    check("c D", not isinstance(c, D), True)
    check("foo E", not isinstance('foo', E), True)


class BadSeq:
    def __len__(self) -> int:
        raise ValueError


class NegativeLen:
    def __len__(self) -> int:
        return -10


class HugeNegativeLen:
    def __len__(self) -> int:
        return -sys.maxsize-10


def test_len() -> None:
    check("len('123')", len('123'), 3)
    check("len(())", len(()), 0)
    check("len((1, 2, 3, 4))", len((1, 2, 3, 4)), 4)
    check("len([1, 2, 3, 4])", len([1, 2, 3, 4]), 4)
    e: dict[str, int] = {}
    check("len({})", len(e), 0)
    check("len({'a':1, 'b': 2})", len({'a':1, 'b': 2}), 2)
    try:
        len(BadSeq())
    except ValueError as ex:
        print("ValueError", ex)
    try:
        len(NegativeLen())
    except ValueError as ex:
        print("ValueError", ex)


class Iter(object):
    def __iter__(self):
        return self
    def __next__(self) -> int:
        raise StopIteration


def test_next() -> None:
    it = iter(range(2))
    check("next", next(it), 0)
    check("next", next(it), 1)
    try:
        next(it)
    except StopIteration:
        print("StopIteration")
    try:
        next(it)
    except StopIteration:
        print("StopIteration")
    check("next default", next(it, 42), 42)
    it2 = iter(Iter())
    check("next default", next(it2, 42), 42)
    try:
        next(it2)
    except StopIteration:
        print("StopIteration")


def test_ord() -> None:
    check("ord(' ')", ord(' '), 32)
    check("ord('A')", ord('A'), 65)
    check("ord('a')", ord('a'), 97)
    check("ord('\x80')", ord('\x80'), 128)
    check("ord('\xff')", ord('\xff'), 255)
    check("0x10FFFF", ord(chr(0x10FFFF)), 0x10FFFF)
    check("0xFFFF", ord("\U0000FFFF"), 0x0000FFFF)
    check("0x10000", ord("\U00010000"), 0x00010000)
    check("0x10001", ord("\U00010001"), 0x00010001)
    check("0xFFFFE", ord("\U000FFFFE"), 0x000FFFFE)
    check("0xFFFFF", ord("\U000FFFFF"), 0x000FFFFF)
    check("0x100000", ord("\U00100000"), 0x00100000)
    check("0x100001", ord("\U00100001"), 0x00100001)
    check("0x10FFFE", ord("\U0010FFFE"), 0x0010FFFE)
    check("0x10FFFF", ord("\U0010FFFF"), 0x0010FFFF)


def test_pow() -> None:
    check("pow(0,0)", pow(0,0), 1)
    check("pow(0,1)", pow(0,1), 0)
    check("pow(1,0)", pow(1,0), 1)
    check("pow(1,1)", pow(1,1), 1)
    check("pow(2,0)", pow(2,0), 1)
    check("pow(2,10)", pow(2,10), 1024)
    check("pow(2,20)", pow(2,20), 1024*1024)
    check("pow(2,30)", pow(2,30), 1024*1024*1024)
    check("pow(-2,0)", pow(-2,0), 1)
    check("pow(-2,1)", pow(-2,1), -2)
    check("pow(-2,2)", pow(-2,2), 4)
    check("pow(-2,3)", pow(-2,3), -8)
    check("pow(0.,0)", pow(0.,0), 1.)
    check("pow(0.,1)", pow(0.,1), 0.)
    check("pow(1.,0)", pow(1.,0), 1.)
    check("pow(1.,1)", pow(1.,1), 1.)
    check("pow(2.,0)", pow(2.,0), 1.)
    check("pow(2.,10)", pow(2.,10), 1024.)
    check("pow(2.,20)", pow(2.,20), 1024.*1024.)
    check("pow(2.,30)", pow(2.,30), 1024.*1024.*1024.)
    check("pow(-2.,0)", pow(-2.,0), 1.)
    check("pow(-2.,1)", pow(-2.,1), -2.)
    check("pow(-2.,2)", pow(-2.,2), 4.)
    check("pow(-2.,3)", pow(-2.,3), -8.)
    check("pow(2, 10, 1000)", pow(2, 10, 1000), 24)
    check("pow(-1, -2, 3)", pow(-1, -2, 3), 1)
    try:
        pow(1, 2, 0)
    except ValueError as e:
        print("ValueError:", e)


test_abs()
test_callable()
test_chr()
test_divmod()
test_hash()
test_hex_oct_bin()
test_isinstance()
test_len()
test_next()
test_ord()
test_pow()
