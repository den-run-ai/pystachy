# Adapted from CPython 3.13.16 Lib/test/test_int.py, class IntTestCases: test_basic,
# test_invalid_signs, test_unicode, test_underscores, test_no_args, test_keyword_args,
# test_int_base_limits, test_int_base_indexable, test_string_float, test_error_message and
# test_issue31619 (with test.support.numbers' VALID_UNDERSCORE_LITERALS and
# INVALID_UNDERSCORE_LITERALS); and Lib/test/test_long.py, class LongTest: test_long and
# test_nan_inf; commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertRaises a try statement that prints the exception. A table holds one type here:
# in L, the expected ValueError is None. test_underscores' eval(lit) is a dict of the literals,
# written as code; test_error_message checks str() of the ValueError, which is its args[0].
# "\N{EM SPACE}" and "\N{EN SPACE}" are written "\u2003" and "\u2002" (\N{...} is rejected:
# #122).
# test_long's 2**63 - 1 and -2**63 bases are written as their values (2**63 does not fit).
# EXCLUDED upstream cases (ints are 64-bit here, and the bases, results and inputs that need more
# raise OverflowError, a documented deviation):
# - test_basic's int(s[1:]) == sys.maxsize + 1, int(1e100), int(-1e100) and int('1' * 600);
#   test_unicode's int("१२३४५६७८९०1234567890") (also with base 0), 12345678901234567890;
#   test_int_base_limits' bases 0-(2**234) and 2**234; test_int_base_indexable's 2**100 and
#   -2**100; test_long's LL (10**20 and 10**100) and its bases 2**63, -2**63-1, 2**100, -2**100
# - test_basic's int(1, 12): a compile-time error with CPython's message
#   (tests/errors/upstream/upstream_int_base_non_str.py); int("10", 2, 1): a compile-time error worded
#   "int() takes at most 2 arguments (3 given)", where CPython says "int expected at most 2
#   arguments, got 3" (bug: message wording, as #277's)
# - test_keyword_args' int(x=1.2) and int(x='100', base=2): compile-time errors worded "keyword
#   argument 'x' of int() is not supported", where CPython says "int() got an unexpected keyword
#   argument 'x'" (bug: message wording, as #277's); int(base=10) and int(base=0) are
#   tests/errors/upstream/upstream_int_missing_string*.py (CPython's message)
# - test_underscores' int(b"1_00"), test_non_numeric_input_types and test_int_memoryview (bytes,
#   bytearray, memoryview, array, str subclasses), and test_error_message's bytes cases
# - test_int_base_bad_types (int('0', 5.5): rejected at compile time, "unsupported call
#   int(str,float)"), test_int_base_indexable's MyIndexable (__index__ is not supported)
# - test_small_ints (`is` between ints is rejected), test_intconversion (int() of objects whose
#   classes define __int__, __index__ or __trunc__: rejected at compile time, with the message
#   CPython gives where the class defines none of them; a bug, NEW), test_int_subclass_with_index,
#   test_int_subclass_with_int and test_int_returns_int_subclass (subclasses of int)
# - IntStrDigitLimitsTests and IntSubclassStrDigitLimitsTests (sys.get_int_max_str_digits() and
#   set_int_max_str_digits() are not supported; their values have thousands of digits; Pystachy
#   checks CPython's default limit of 4300 digits: tests/programs/runtime/rt_int_digit_limit.py), and
#   PyLongModuleTests (_pylong, ints of 30,000 to 1,000,000 digits)
import sys


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def int_raises(s: str, base: int | None = None) -> None:
    # assertRaises(ValueError, int, s[, base])
    try:
        if base is None:
            v = int(s)
        else:
            v = int(s, base)
    except ValueError as e:
        print("int(%r, %r) ValueError: %s" % (s, base, e))
    else:
        assert False, "expected ValueError, got %d" % v


L: list[tuple[str, int | None]] = [
    ('0', 0),
    ('1', 1),
    ('9', 9),
    ('10', 10),
    ('99', 99),
    ('100', 100),
    ('314', 314),
    (' 314', 314),
    ('314 ', 314),
    ('  \t\t  314  \t\t  ', 314),
    (repr(sys.maxsize), sys.maxsize),
    ('  1x', None),  # ValueError
    ('  1  ', 1),
    ('  1\02  ', None),
    ('', None),
    (' ', None),
    ('  \t\t  ', None),
    ("\u0200", None)
]


def test_basic() -> None:
    check("int(314)", int(314), 314)
    check("int(3.14)", int(3.14), 3)
    # Check that conversion from float truncates towards zero
    check("int(-3.14)", int(-3.14), -3)
    check("int(3.9)", int(3.9), 3)
    check("int(-3.9)", int(-3.9), -3)
    check("int(3.5)", int(3.5), 3)
    check("int(-3.5)", int(-3.5), -3)
    check('int("-3")', int("-3"), -3)
    check('int(" -3 ")', int(" -3 "), -3)
    check('int("\\N{EM SPACE}-3\\N{EN SPACE}")', int("\u2003-3\u2002"), -3)
    # Different base:
    check('int("10",16)', int("10",16), 16)
    # Test conversion from strings and various anomalies
    for s, v in L:
        for sign in "", "+", "-":
            for prefix in "", " ", "\t", "  \t\t  ":
                ss = prefix + sign + s
                vv = v
                if sign == "-" and v is not None:
                    vv = -v
                try:
                    check("int(%r)" % ss, int(ss), vv)
                except ValueError:
                    print("int(%r) ValueError" % ss)

    s = repr(-1-sys.maxsize)
    x = int(s)
    check("x+1", x+1, -sys.maxsize)
    check("isinstance(x, int)", isinstance(x, int), True)

    # SF bug 434186:  0x80000000/2 != 0x80000000>>1.
    # Worked by accident in Windows release build, but failed in debug build.
    # Failed in all Linux builds.
    x = -1-sys.maxsize
    check("x >> 1", x >> 1, x//2)

    check("int('0o123', 0)", int('0o123', 0), 83)
    check("int('0x123', 16)", int('0x123', 16), 291)

    # Bug 1679: "0x" is not a valid hex literal
    int_raises("0x", 16)
    int_raises("0x", 0)

    int_raises("0o", 8)
    int_raises("0o", 0)

    int_raises("0b", 2)
    int_raises("0b", 0)

    # SF bug 1334662: int(string, base) wrong answers
    # Various representations of 2**32 evaluated to 0
    # rather than 2**32 in previous versions

    check("int('100000000000000000000000000000000', 2)",
          int('100000000000000000000000000000000', 2), 4294967296)
    check("int('102002022201221111211', 3)", int('102002022201221111211', 3), 4294967296)
    check("int('10000000000000000', 4)", int('10000000000000000', 4), 4294967296)
    check("int('32244002423141', 5)", int('32244002423141', 5), 4294967296)
    check("int('1550104015504', 6)", int('1550104015504', 6), 4294967296)
    check("int('211301422354', 7)", int('211301422354', 7), 4294967296)
    check("int('40000000000', 8)", int('40000000000', 8), 4294967296)
    check("int('12068657454', 9)", int('12068657454', 9), 4294967296)
    check("int('4294967296', 10)", int('4294967296', 10), 4294967296)
    check("int('1904440554', 11)", int('1904440554', 11), 4294967296)
    check("int('9ba461594', 12)", int('9ba461594', 12), 4294967296)
    check("int('535a79889', 13)", int('535a79889', 13), 4294967296)
    check("int('2ca5b7464', 14)", int('2ca5b7464', 14), 4294967296)
    check("int('1a20dcd81', 15)", int('1a20dcd81', 15), 4294967296)
    check("int('100000000', 16)", int('100000000', 16), 4294967296)
    check("int('a7ffda91', 17)", int('a7ffda91', 17), 4294967296)
    check("int('704he7g4', 18)", int('704he7g4', 18), 4294967296)
    check("int('4f5aff66', 19)", int('4f5aff66', 19), 4294967296)
    check("int('3723ai4g', 20)", int('3723ai4g', 20), 4294967296)
    check("int('281d55i4', 21)", int('281d55i4', 21), 4294967296)
    check("int('1fj8b184', 22)", int('1fj8b184', 22), 4294967296)
    check("int('1606k7ic', 23)", int('1606k7ic', 23), 4294967296)
    check("int('mb994ag', 24)", int('mb994ag', 24), 4294967296)
    check("int('hek2mgl', 25)", int('hek2mgl', 25), 4294967296)
    check("int('dnchbnm', 26)", int('dnchbnm', 26), 4294967296)
    check("int('b28jpdm', 27)", int('b28jpdm', 27), 4294967296)
    check("int('8pfgih4', 28)", int('8pfgih4', 28), 4294967296)
    check("int('76beigg', 29)", int('76beigg', 29), 4294967296)
    check("int('5qmcpqg', 30)", int('5qmcpqg', 30), 4294967296)
    check("int('4q0jto4', 31)", int('4q0jto4', 31), 4294967296)
    check("int('4000000', 32)", int('4000000', 32), 4294967296)
    check("int('3aokq94', 33)", int('3aokq94', 33), 4294967296)
    check("int('2qhxjli', 34)", int('2qhxjli', 34), 4294967296)
    check("int('2br45qb', 35)", int('2br45qb', 35), 4294967296)
    check("int('1z141z4', 36)", int('1z141z4', 36), 4294967296)

    # tests with base 0
    # this fails on 3.0, but in 2.x the old octal syntax is allowed
    check("int(' 0o123  ', 0)", int(' 0o123  ', 0), 83)
    check("int(' 0o123  ', 0)", int(' 0o123  ', 0), 83)
    check("int('000', 0)", int('000', 0), 0)
    check("int('0o123', 0)", int('0o123', 0), 83)
    check("int('0x123', 0)", int('0x123', 0), 291)
    check("int('0b100', 0)", int('0b100', 0), 4)
    check("int(' 0O123   ', 0)", int(' 0O123   ', 0), 83)
    check("int(' 0X123  ', 0)", int(' 0X123  ', 0), 291)
    check("int(' 0B100 ', 0)", int(' 0B100 ', 0), 4)
    int_raises('010', 0)

    # without base still base 10
    check("int('0123')", int('0123'), 123)
    check("int('0123', 10)", int('0123', 10), 123)

    # tests with prefix and base != 0
    check("int('0x123', 16)", int('0x123', 16), 291)
    check("int('0o123', 8)", int('0o123', 8), 83)
    check("int('0b100', 2)", int('0b100', 2), 4)
    check("int('0X123', 16)", int('0X123', 16), 291)
    check("int('0O123', 8)", int('0O123', 8), 83)
    check("int('0B100', 2)", int('0B100', 2), 4)

    # the code has special checks for the first character after the
    #  type prefix
    int_raises('0b2', 2)
    int_raises('0b02', 2)
    int_raises('0B2', 2)
    int_raises('0B02', 2)
    int_raises('0o8', 8)
    int_raises('0o08', 8)
    int_raises('0O8', 8)
    int_raises('0O08', 8)
    int_raises('0xg', 16)
    int_raises('0x0g', 16)
    int_raises('0Xg', 16)
    int_raises('0X0g', 16)

    # SF bug 1334662: int(string, base) wrong answers
    # Checks for proper evaluation of 2**32 + 1
    check("int('100000000000000000000000000000001', 2)",
          int('100000000000000000000000000000001', 2), 4294967297)
    check("int('102002022201221111212', 3)", int('102002022201221111212', 3), 4294967297)
    check("int('10000000000000001', 4)", int('10000000000000001', 4), 4294967297)
    check("int('32244002423142', 5)", int('32244002423142', 5), 4294967297)
    check("int('1550104015505', 6)", int('1550104015505', 6), 4294967297)
    check("int('211301422355', 7)", int('211301422355', 7), 4294967297)
    check("int('40000000001', 8)", int('40000000001', 8), 4294967297)
    check("int('12068657455', 9)", int('12068657455', 9), 4294967297)
    check("int('4294967297', 10)", int('4294967297', 10), 4294967297)
    check("int('1904440555', 11)", int('1904440555', 11), 4294967297)
    check("int('9ba461595', 12)", int('9ba461595', 12), 4294967297)
    check("int('535a7988a', 13)", int('535a7988a', 13), 4294967297)
    check("int('2ca5b7465', 14)", int('2ca5b7465', 14), 4294967297)
    check("int('1a20dcd82', 15)", int('1a20dcd82', 15), 4294967297)
    check("int('100000001', 16)", int('100000001', 16), 4294967297)
    check("int('a7ffda92', 17)", int('a7ffda92', 17), 4294967297)
    check("int('704he7g5', 18)", int('704he7g5', 18), 4294967297)
    check("int('4f5aff67', 19)", int('4f5aff67', 19), 4294967297)
    check("int('3723ai4h', 20)", int('3723ai4h', 20), 4294967297)
    check("int('281d55i5', 21)", int('281d55i5', 21), 4294967297)
    check("int('1fj8b185', 22)", int('1fj8b185', 22), 4294967297)
    check("int('1606k7id', 23)", int('1606k7id', 23), 4294967297)
    check("int('mb994ah', 24)", int('mb994ah', 24), 4294967297)
    check("int('hek2mgm', 25)", int('hek2mgm', 25), 4294967297)
    check("int('dnchbnn', 26)", int('dnchbnn', 26), 4294967297)
    check("int('b28jpdn', 27)", int('b28jpdn', 27), 4294967297)
    check("int('8pfgih5', 28)", int('8pfgih5', 28), 4294967297)
    check("int('76beigh', 29)", int('76beigh', 29), 4294967297)
    check("int('5qmcpqh', 30)", int('5qmcpqh', 30), 4294967297)
    check("int('4q0jto5', 31)", int('4q0jto5', 31), 4294967297)
    check("int('4000001', 32)", int('4000001', 32), 4294967297)
    check("int('3aokq95', 33)", int('3aokq95', 33), 4294967297)
    check("int('2qhxjlj', 34)", int('2qhxjlj', 34), 4294967297)
    check("int('2br45qc', 35)", int('2br45qc', 35), 4294967297)
    check("int('1z141z5', 36)", int('1z141z5', 36), 4294967297)


def test_invalid_signs() -> None:
    int_raises('+')
    int_raises('-')
    int_raises('- 1')
    int_raises('+ 1')
    int_raises(' + 1 ')


def test_unicode() -> None:
    check("int('١٢٣٤٥٦٧٨٩٠')", int('١٢٣٤٥٦٧٨٩٠'), 1234567890)
    check("int('١٢٣٤٥٦٧٨٩٠', 0)", int('١٢٣٤٥٦٧٨٩٠', 0), 1234567890)


VALID_UNDERSCORE_LITERALS = [
    '0_0_0',
    '4_2',
    '1_0000_0000',
    '0b1001_0100',
    '0xffff_ffff',
    '0o5_7_7',
    '1_00_00.5',
    '1_00_00.5e5',
    '1_00_00e5_1',
    '1e1_0',
    '.1_4',
    '.1_4e1',
    '0b_0',
    '0x_f',
    '0o_5',
    '1_00_00j',
    '1_00_00.5j',
    '1_00_00e5_1j',
    '.1_4j',
    '(1_2.5+3_3j)',
    '(.5_6j)',
]
INVALID_UNDERSCORE_LITERALS = [
    # Trailing underscores:
    '0_',
    '42_',
    '1.4j_',
    '0x_',
    '0b1_',
    '0xf_',
    '0o5_',
    '0 if 1_Else 1',
    # Underscores in the base selector:
    '0_b0',
    '0_xf',
    '0_o5',
    # Old-style octal, still disallowed:
    '0_7',
    '09_99',
    # Multiple consecutive underscores:
    '4_______2',
    '0.1__4',
    '0.1__4j',
    '0b1001__0100',
    '0xffff__ffff',
    '0x___',
    '0o5__77',
    '1e1__0',
    '1e1__0j',
    # Underscore right before a dot:
    '1_.4',
    '1_.4j',
    # Underscore right after a dot:
    '1._4',
    '1._4j',
    '._5',
    '._5j',
    # Underscore right after a sign:
    '1.0e+_1',
    '1.0e+_1j',
    # Underscore right before j:
    '1.4_j',
    '1.4e5_j',
    # Underscore right before e:
    '1_e1',
    '1.4_e1',
    '1.4_e1j',
    # Underscore right after e:
    '1e_1',
    '1.4e_1',
    '1.4e_1j',
    # Complex cases with parens:
    '(1+1.5_j_)',
    '(1+1.5_j)',
]
# eval(lit) of the literals that test_underscores evaluates
EVAL = {
    '0_0_0': 0_0_0,
    '4_2': 4_2,
    '1_0000_0000': 1_0000_0000,
    '0b1001_0100': 0b1001_0100,
    '0xffff_ffff': 0xffff_ffff,
    '0o5_7_7': 0o5_7_7,
    '0b_0': 0b_0,
    '0x_f': 0x_f,
    '0o_5': 0o_5,
}


def test_underscores() -> None:
    for lit in VALID_UNDERSCORE_LITERALS:
        if any(ch in lit for ch in '.eEjJ'):
            continue
        check("int(%r, 0)" % lit, int(lit, 0), EVAL[lit])
        check("int(%r, 0)" % lit.replace('_', ''), int(lit, 0), int(lit.replace('_', ''), 0))
    for lit in INVALID_UNDERSCORE_LITERALS:
        if any(ch in lit for ch in '.eEjJ'):
            continue
        int_raises(lit, 0)
    # Additional test cases with bases != 0, only for the constructor:
    check('int("1_00", 3)', int("1_00", 3), 9)
    check('int("0_100")', int("0_100"), 100)  # not valid as a literal!
    int_raises("_100")
    int_raises("+_100")
    int_raises("1__00")
    int_raises("100_")


def test_no_args() -> None:
    check("int()", int(), 0)


def test_keyword_args() -> None:
    # Test invoking int() using keyword arguments.
    check("int('100', base=2)", int('100', base=2), 4)


def test_int_base_limits() -> None:
    """Testing the supported limits of the int() base parameter."""
    check("int('0', 5)", int('0', 5), 0)
    int_raises('0', 1)
    int_raises('0', 37)
    int_raises('0', -909)  # An old magic value base from Python 2.
    # Bases 2 through 36 are supported.
    for base in range(2,37):
        check("int('0', base=%d)" % base, int('0', base=base), 0)


def test_int_base_indexable() -> None:
    # Check out of range bases.
    for base in 1, 37:
        int_raises('43', base)


def test_string_float() -> None:
    int_raises('1.2')


def test_error_message() -> None:
    def check_msg(s: str, base: int | None = None) -> None:
        try:
            if base is None:
                int(s)
            else:
                int(s, base)
        except ValueError as e:
            print("int(%r, %r):" % (s, base), repr(str(e)))
            assert str(e) == "invalid literal for int() with base %d: %r" % (10 if base is None else base, s)
        else:
            assert False, "int(%r, %r)" % (s, base)

    check_msg('\xbd')
    check_msg('123\xbd')
    check_msg('  123 456  ')

    check_msg('123\x00')
    # SF bug 1545497: embedded NULs were not detected with explicit base
    check_msg('123\x00', 10)
    check_msg('123\x00 245', 20)
    check_msg('123\x00 245', 16)
    check_msg('123\x00245', 20)
    check_msg('123\x00245', 16)
    # lone surrogate in Unicode string
    check_msg('123\ud800')
    check_msg('123\ud800', 10)


def test_issue31619() -> None:
    check("int('1_0_1_..._1', 2)", int('1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1', 2),
                     0b1010101010101010101010101010101)
    check("int('1_2_3_4_5_6_7_0_1_2_3', 8)", int('1_2_3_4_5_6_7_0_1_2_3', 8), 0o12345670123)
    check("int('1_2_3_4_5_6_7_8_9', 16)", int('1_2_3_4_5_6_7_8_9', 16), 0x123456789)
    check("int('1_2_3_4_5_6_7', 32)", int('1_2_3_4_5_6_7', 32), 1144132807)


# Lib/test/test_long.py, LongTest
def test_long() -> None:
    # trailing L should no longer be accepted...
    int_raises('123L')
    int_raises('123l')
    int_raises('0L')
    int_raises('-37L')
    int_raises('0x32L', 16)
    int_raises('1L', 21)
    # ... but it's just a normal digit if base >= 22
    check("int('1L', 22)", int('1L', 22), 43)

    # tests with base 0
    check("int('000', 0)", int('000', 0), 0)
    check("int('0o123', 0)", int('0o123', 0), 83)
    check("int('0x123', 0)", int('0x123', 0), 291)
    check("int('0b100', 0)", int('0b100', 0), 4)
    check("int(' 0O123   ', 0)", int(' 0O123   ', 0), 83)
    check("int(' 0X123  ', 0)", int(' 0X123  ', 0), 291)
    check("int(' 0B100 ', 0)", int(' 0B100 ', 0), 4)
    check("int('0', 0)", int('0', 0), 0)
    check("int('+0', 0)", int('+0', 0), 0)
    check("int('-0', 0)", int('-0', 0), 0)
    check("int('00', 0)", int('00', 0), 0)
    int_raises('08', 0)
    int_raises('-012395', 0)

    # invalid bases
    invalid_bases = [-909,
                      2**31-1, 2**31, -2**31, -2**31-1,
                      9223372036854775807, -9223372036854775807-1,  # 2**63-1, -2**63
                      ]
    for base in invalid_bases:
        int_raises('42', base)

    # Invalid unicode string
    # See bpo-34087
    int_raises('\u3053\u3093\u306b\u3061\u306f')


def test_nan_inf() -> None:
    try:
        int(float('inf'))
    except OverflowError as e:
        print("int(float('inf')) OverflowError:", e)
    else:
        assert False, "expected OverflowError"
    try:
        int(float('-inf'))
    except OverflowError as e:
        print("int(float('-inf')) OverflowError:", e)
    else:
        assert False, "expected OverflowError"
    try:
        int(float('nan'))
    except ValueError as e:
        print("int(float('nan')) ValueError:", e)
    else:
        assert False, "expected ValueError"


test_basic()
test_invalid_signs()
test_unicode()
test_underscores()
test_no_args()
test_keyword_args()
test_int_base_limits()
test_int_base_indexable()
test_string_float()
test_error_message()
test_issue31619()
test_long()
test_nan_inf()
