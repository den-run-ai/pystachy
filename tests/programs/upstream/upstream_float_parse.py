# Adapted from CPython 3.13.16 Lib/test/test_float.py, class GeneralFloatCases: test_float,
# test_noargs, test_underscores (with test.support.numbers' VALID_UNDERSCORE_LITERALS and
# INVALID_UNDERSCORE_LITERALS) and test_error_message; and class InfNanTest: test_inf_from_str,
# test_inf_as_str, test_nan_from_str, test_nan_as_str, test_inf_signs and test_nan_signs;
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertTrue(x) prints x and asserts it, assertRaises a try statement that prints the
# exception. test_underscores' eval(lit) is a dict of the literals, written as code, whose values
# are floats (eval() gives an int for '0_0_0', '4_2' and '1_0000_0000', which float(lit) equals);
# test_error_message checks str() of the ValueError. "\N{EM SPACE}" and "\N{EN SPACE}" are
# written "\u2003" and "\u2002" (\N{...} is rejected: #122).
# EXCLUDED upstream cases:
# - test_float's float({}) (TypeError, also with assertRaisesRegex "not 'dict'"): a compile-time
#   error here, worded "unsupported call float(dict[int,int])" where CPython says "float()
#   argument must be a string or a real number, not 'dict'" (as #277's); and
#   float(b'.' + b'1'*1000) (bytes)
# - test_underscores' float(b'0_.\xff9'), test_error_message's bytes cases,
#   test_non_numeric_input_types and test_float_memoryview (bytes, bytearray, memoryview, array,
#   str subclasses)
# - test_float_with_comma (locale; upstream skips it where the locale's decimal point is '.')
# - test_keyword_args (float(x='3.14'): a compile-time error worded "keyword argument 'x' of
#   float() is not supported" where CPython says "float() takes no keyword arguments", as
#   #277's), test_keywords_in_subclass (subclasses of float)
# - the other GeneralFloatCases methods are in tests/programs/upstream/upstream_float_ops.py, or listed there
from math import isinf, isnan, copysign


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_true(label: str, got: bool) -> None:
    print(label, repr(got))
    assert got, label


def float_raises(s: str) -> None:
    # assertRaises(ValueError, float, s)
    try:
        v = float(s)
    except ValueError as e:
        print("float(%r) ValueError: %s" % (s, e))
    else:
        assert False, "expected ValueError, got %r" % v


def test_float() -> None:
    check("float(3.14)", float(3.14), 3.14)
    check("float(314)", float(314), 314.0)
    check('float("  3.14  ")', float("  3.14  "), 3.14)
    float_raises("  0x3.1  ")
    float_raises("  -0x3.p-1  ")
    float_raises("  +0x3.p-1  ")
    float_raises("++3.14")
    float_raises("+-3.14")
    float_raises("-+3.14")
    float_raises("--3.14")
    float_raises(".nan")
    float_raises("+.inf")
    float_raises(".")
    float_raises("-.")
    # Lone surrogate
    float_raises('\uD8F0')
    # check that we don't accept alternate exponent markers
    float_raises("-1.7d29")
    float_raises("3D-14")
    check('float("  \\u0663.\\u0661\\u0664  ")', float("  \u0663.\u0661\u0664  "), 3.14)
    check('float("\\N{EM SPACE}3.14\\N{EN SPACE}")', float("\u20033.14\u2002"), 3.14)
    # extra long strings should not be a problem
    print("float('.' + '1'*1000)", float('.' + '1'*1000))
    # Invalid unicode string
    # See bpo-34087
    float_raises('\u3053\u3093\u306b\u3061\u306f')


def test_noargs() -> None:
    check("float()", float(), 0.0)


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
    '0_0_0': float(0_0_0),
    '4_2': float(4_2),
    '1_0000_0000': float(1_0000_0000),
    '1_00_00.5': 1_00_00.5,
    '1_00_00.5e5': 1_00_00.5e5,
    '1_00_00e5_1': 1_00_00e5_1,
    '1e1_0': 1e1_0,
    '.1_4': .1_4,
    '.1_4e1': .1_4e1,
}


def test_underscores() -> None:
    for lit in VALID_UNDERSCORE_LITERALS:
        if not any(ch in lit for ch in 'jJxXoObB'):
            check("float(%r)" % lit, float(lit), EVAL[lit])
            check("float(%r)" % lit.replace('_', ''), float(lit), float(lit.replace('_', '')))
    for lit in INVALID_UNDERSCORE_LITERALS:
        if lit in ('0_7', '09_99'):  # octals are not recognized here
            continue
        if not any(ch in lit for ch in 'jJxXoObB'):
            float_raises(lit)
    # Additional test cases; nan and inf are never valid as literals,
    # only in the float() constructor, but we don't allow underscores
    # in or around them.
    float_raises('_NaN')
    float_raises('Na_N')
    float_raises('IN_F')
    float_raises('-_INF')
    float_raises('-INF_')


def test_error_message() -> None:
    def check_msg(s: str) -> None:
        try:
            float(s)
        except ValueError as e:
            print("float(%r):" % s, repr(str(e)))
            assert str(e) == 'could not convert string to float: %r' % (s,)
        else:
            assert False, 'float(%r)' % (s,)

    check_msg('\xbd')
    check_msg('123\xbd')
    check_msg('  123 456  ')
    # all whitespace (cf. https://github.com/python/cpython/issues/95605)
    check_msg('')
    check_msg(' ')
    check_msg('\t \n')

    # non-ascii digits (error came from non-digit '!')
    check_msg('\u0663\u0661\u0664!')
    # embedded NUL
    check_msg('123\x00')
    check_msg('123\x00 245')
    check_msg('123\x00245')


# Beginning with Python 2.6 float has cross platform compatible
# ways to create and represent inf and nan
def test_inf_from_str() -> None:
    check_true('isinf(float("inf"))', isinf(float("inf")))
    check_true('isinf(float("+inf"))', isinf(float("+inf")))
    check_true('isinf(float("-inf"))', isinf(float("-inf")))
    check_true('isinf(float("infinity"))', isinf(float("infinity")))
    check_true('isinf(float("+infinity"))', isinf(float("+infinity")))
    check_true('isinf(float("-infinity"))', isinf(float("-infinity")))

    check('repr(float("inf"))', repr(float("inf")), "inf")
    check('repr(float("+inf"))', repr(float("+inf")), "inf")
    check('repr(float("-inf"))', repr(float("-inf")), "-inf")
    check('repr(float("infinity"))', repr(float("infinity")), "inf")
    check('repr(float("+infinity"))', repr(float("+infinity")), "inf")
    check('repr(float("-infinity"))', repr(float("-infinity")), "-inf")

    check('repr(float("INF"))', repr(float("INF")), "inf")
    check('repr(float("+Inf"))', repr(float("+Inf")), "inf")
    check('repr(float("-iNF"))', repr(float("-iNF")), "-inf")
    check('repr(float("Infinity"))', repr(float("Infinity")), "inf")
    check('repr(float("+iNfInItY"))', repr(float("+iNfInItY")), "inf")
    check('repr(float("-INFINITY"))', repr(float("-INFINITY")), "-inf")

    check('str(float("inf"))', str(float("inf")), "inf")
    check('str(float("+inf"))', str(float("+inf")), "inf")
    check('str(float("-inf"))', str(float("-inf")), "-inf")
    check('str(float("infinity"))', str(float("infinity")), "inf")
    check('str(float("+infinity"))', str(float("+infinity")), "inf")
    check('str(float("-infinity"))', str(float("-infinity")), "-inf")

    float_raises("info")
    float_raises("+info")
    float_raises("-info")
    float_raises("in")
    float_raises("+in")
    float_raises("-in")
    float_raises("infinit")
    float_raises("+Infin")
    float_raises("-INFI")
    float_raises("infinitys")

    float_raises("++Inf")
    float_raises("-+inf")
    float_raises("+-infinity")
    float_raises("--Infinity")


def test_inf_as_str() -> None:
    check("repr(1e300 * 1e300)", repr(1e300 * 1e300), "inf")
    check("repr(-1e300 * 1e300)", repr(-1e300 * 1e300), "-inf")

    check("str(1e300 * 1e300)", str(1e300 * 1e300), "inf")
    check("str(-1e300 * 1e300)", str(-1e300 * 1e300), "-inf")


def test_nan_from_str() -> None:
    check_true('isnan(float("nan"))', isnan(float("nan")))
    check_true('isnan(float("+nan"))', isnan(float("+nan")))
    check_true('isnan(float("-nan"))', isnan(float("-nan")))

    check('repr(float("nan"))', repr(float("nan")), "nan")
    check('repr(float("+nan"))', repr(float("+nan")), "nan")
    check('repr(float("-nan"))', repr(float("-nan")), "nan")

    check('repr(float("NAN"))', repr(float("NAN")), "nan")
    check('repr(float("+NAn"))', repr(float("+NAn")), "nan")
    check('repr(float("-NaN"))', repr(float("-NaN")), "nan")

    check('str(float("nan"))', str(float("nan")), "nan")
    check('str(float("+nan"))', str(float("+nan")), "nan")
    check('str(float("-nan"))', str(float("-nan")), "nan")

    float_raises("nana")
    float_raises("+nana")
    float_raises("-nana")
    float_raises("na")
    float_raises("+na")
    float_raises("-na")

    float_raises("++nan")
    float_raises("-+NAN")
    float_raises("+-NaN")
    float_raises("--nAn")


def test_nan_as_str() -> None:
    check("repr(1e300 * 1e300 * 0)", repr(1e300 * 1e300 * 0), "nan")
    check("repr(-1e300 * 1e300 * 0)", repr(-1e300 * 1e300 * 0), "nan")

    check("str(1e300 * 1e300 * 0)", str(1e300 * 1e300 * 0), "nan")
    check("str(-1e300 * 1e300 * 0)", str(-1e300 * 1e300 * 0), "nan")


def test_inf_signs() -> None:
    check("copysign(1.0, float('inf'))", copysign(1.0, float('inf')), 1.0)
    check("copysign(1.0, float('-inf'))", copysign(1.0, float('-inf')), -1.0)


def test_nan_signs() -> None:
    # The sign of float('nan') should be predictable.
    check("copysign(1.0, float('nan'))", copysign(1.0, float('nan')), 1.0)
    check("copysign(1.0, float('-nan'))", copysign(1.0, float('-nan')), -1.0)


test_float()
test_noargs()
test_underscores()
test_error_message()
test_inf_from_str()
test_inf_as_str()
test_nan_from_str()
test_nan_as_str()
test_inf_signs()
test_nan_signs()
