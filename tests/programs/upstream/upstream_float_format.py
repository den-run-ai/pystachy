# Adapted from CPython 3.13.16 Lib/test/test_float.py, class FormatTestCase: test_format,
# test_format_testfile (with Lib/test/mathdata/formatfloat_testcases.txt, below), test_issue5864
# and test_issue35560; and class RoundTestCase: test_inf_nan, test_inf_nan_ndigits, test_large_n,
# test_small_n, test_overflow, test_previous_round_bugs, test_matches_float_format,
# test_format_specials and test_None_ndigits (with test.support.testcase's
# FloatsAreIdenticalMixin.assertFloatsAreIdentical); commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertTrue(x) prints x and asserts it, assertRaises a try statement that prints the
# exception. Where upstream loops over hundreds of values, each assertion is an assert and the
# loop prints how many it checked. test_format_testfile reads the test file's text from a
# string, FORMAT_TESTCASES. fmt % x, where fmt is a variable (a % format is a literal here), is
# pct(fmt, x), which formats with the literal of each format the tests use; and its
# map(str.strip, ...), which only consumers such as list() take here, is a comprehension.
# random is seeded, so that test_matches_float_format's random.random() draws the same values on
# every run.
# EXCLUDED upstream cases:
# - test_inf_nan's TypeErrors (round(INF, 0.0), round(-INF, 1.0), round(NAN, "ceci n'est pas un
#   integer"), round(-0.0, 1j)): compile-time errors here, worded "unsupported call
#   round(float,float)" and "unsupported call round(float,str)" where CPython says "'float' object
#   cannot be interpreted as an integer" (as #277's; and complex numbers are not supported)
# - test_large_n's and test_small_n's n of 2**100 and -2**100 (ints are 64-bit here)
# - test_None_ndigits' round(1.23, ndigits=None) and round(1.78, ndigits=None) (a compile-time
#   error: "keyword argument 'ndigits' of round() is not supported"; docs/language.md rejects a
#   keyword argument Pystachy does not take)
# - FormatFunctionsTestCase.test_getformat (float.__getformat__ is not supported), and
#   IEEEFormatTestCase's test_double_specials_do_unpack, test_float_specials_do_unpack and
#   test_serialized_float_rounding (struct, _testcapi)
# - ReprTestCase is tests/programs/upstream/upstream_float_repr.py; HexFloatTestCase's test_ends,
#   test_invalid_inputs, test_whitespace, test_from_hex, test_roundtrip and test_subclass:
#   float.fromhex() is not supported (float.hex() is; each of them needs fromhex())
import math
from math import isnan, copysign
import random

INF = float("inf")
NAN = float("nan")


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_true(label: str, got: bool) -> None:
    print(label, repr(got))
    assert got, label


def assertFloatsAreIdentical(label: str, x: float, y: float) -> None:
    """Fail unless floats x and y are identical, in the sense that:
    (1) both x and y are nans, or
    (2) both x and y are infinities, with the same sign, or
    (3) both x and y are zeros, with the same sign, or
    (4) x and y are both finite and nonzero, and x == y

    """
    print(label, repr(x))
    msg = 'floats %r and %r are not identical' % (x, y)

    if isnan(x) or isnan(y):
        if isnan(x) and isnan(y):
            return
    elif x == y:
        if x != 0.0:
            return
        # both zero; check that signs match
        elif copysign(1.0, x) == copysign(1.0, y):
            return
        else:
            msg += ': zeros have different signs'
    assert False, msg


random.seed(5)


# Lib/test/mathdata/formatfloat_testcases.txt, which test_format_testfile reads
FORMAT_TESTCASES = """\
-- 'f' code formatting, with explicit precision (>= 0).  Output always
-- has the given number of places after the point;  zeros are added if
-- necessary to make this true.

-- zeros
%.0f 0 -> 0
%.1f 0 -> 0.0
%.2f 0 -> 0.00
%.3f 0 -> 0.000
%.50f 0 -> 0.00000000000000000000000000000000000000000000000000

-- precision 0;  result should never include a .
%.0f 1.5 -> 2
%.0f 2.5 -> 2
%.0f 3.5 -> 4
%.0f 0.0 -> 0
%.0f 0.1 -> 0
%.0f 0.001 -> 0
%.0f 10.0 -> 10
%.0f 10.1 -> 10
%.0f 10.01 -> 10
%.0f 123.456 -> 123
%.0f 1234.56 -> 1235
%.0f 1e49 -> 9999999999999999464902769475481793196872414789632
%.0f 9.9999999999999987e+49 -> 99999999999999986860582406952576489172979654066176
%.0f 1e50 -> 100000000000000007629769841091887003294964970946560

-- precision 1
%.1f 0.0001 -> 0.0
%.1f 0.001 -> 0.0
%.1f 0.01 -> 0.0
%.1f 0.04 -> 0.0
%.1f 0.06 -> 0.1
%.1f 0.25 -> 0.2
%.1f 0.75 -> 0.8
%.1f 1.4 -> 1.4
%.1f 1.5 -> 1.5
%.1f 10.0 -> 10.0
%.1f 1000.03 -> 1000.0
%.1f 1234.5678 -> 1234.6
%.1f 1234.7499 -> 1234.7
%.1f 1234.75 -> 1234.8

-- precision 2
%.2f 0.0001 -> 0.00
%.2f 0.001 -> 0.00
%.2f 0.004999 -> 0.00
%.2f 0.005001 -> 0.01
%.2f 0.01 -> 0.01
%.2f 0.125 -> 0.12
%.2f 0.375 -> 0.38
%.2f 1234500 -> 1234500.00
%.2f 1234560 -> 1234560.00
%.2f 1234567 -> 1234567.00
%.2f 1234567.8 -> 1234567.80
%.2f 1234567.89 -> 1234567.89
%.2f 1234567.891 -> 1234567.89
%.2f 1234567.8912 -> 1234567.89

-- alternate form always includes a decimal point.  This only
-- makes a difference when the precision is 0.
%#.0f 0 -> 0.
%#.1f 0 -> 0.0
%#.0f 1.5 -> 2.
%#.0f 2.5 -> 2.
%#.0f 10.1 -> 10.
%#.0f 1234.56 -> 1235.
%#.1f 1.4 -> 1.4
%#.2f 0.375 -> 0.38

-- if precision is omitted it defaults to 6
%f 0 -> 0.000000
%f 1230000 -> 1230000.000000
%f 1234567 -> 1234567.000000
%f 123.4567 -> 123.456700
%f 1.23456789 -> 1.234568
%f 0.00012 -> 0.000120
%f 0.000123 -> 0.000123
%f 0.00012345 -> 0.000123
%f 0.000001 -> 0.000001
%f 0.0000005001 -> 0.000001
%f 0.0000004999 -> 0.000000

-- 'e' code formatting with explicit precision (>= 0). Output should
-- always have exactly the number of places after the point that were
-- requested.

-- zeros
%.0e 0 -> 0e+00
%.1e 0 -> 0.0e+00
%.2e 0 -> 0.00e+00
%.10e 0 -> 0.0000000000e+00
%.50e 0 -> 0.00000000000000000000000000000000000000000000000000e+00

-- precision 0.  no decimal point in the output
%.0e 0.01 -> 1e-02
%.0e 0.1 -> 1e-01
%.0e 1 -> 1e+00
%.0e 10 -> 1e+01
%.0e 100 -> 1e+02
%.0e 0.012 -> 1e-02
%.0e 0.12 -> 1e-01
%.0e 1.2 -> 1e+00
%.0e 12 -> 1e+01
%.0e 120 -> 1e+02
%.0e 123.456 -> 1e+02
%.0e 0.000123456 -> 1e-04
%.0e 123456000 -> 1e+08
%.0e 0.5 -> 5e-01
%.0e 1.4 -> 1e+00
%.0e 1.5 -> 2e+00
%.0e 1.6 -> 2e+00
%.0e 2.4999999 -> 2e+00
%.0e 2.5 -> 2e+00
%.0e 2.5000001 -> 3e+00
%.0e 3.499999999999 -> 3e+00
%.0e 3.5 -> 4e+00
%.0e 4.5 -> 4e+00
%.0e 5.5 -> 6e+00
%.0e 6.5 -> 6e+00
%.0e 7.5 -> 8e+00
%.0e 8.5 -> 8e+00
%.0e 9.4999 -> 9e+00
%.0e 9.5 -> 1e+01
%.0e 10.5 -> 1e+01
%.0e 14.999 -> 1e+01
%.0e 15 -> 2e+01

-- precision 1
%.1e 0.0001 -> 1.0e-04
%.1e 0.001 -> 1.0e-03
%.1e 0.01 -> 1.0e-02
%.1e 0.1 -> 1.0e-01
%.1e 1 -> 1.0e+00
%.1e 10 -> 1.0e+01
%.1e 100 -> 1.0e+02
%.1e 120 -> 1.2e+02
%.1e 123 -> 1.2e+02
%.1e 123.4 -> 1.2e+02

-- precision 2
%.2e 0.00013 -> 1.30e-04
%.2e 0.000135 -> 1.35e-04
%.2e 0.0001357 -> 1.36e-04
%.2e 0.0001 -> 1.00e-04
%.2e 0.001 -> 1.00e-03
%.2e 0.01 -> 1.00e-02
%.2e 0.1 -> 1.00e-01
%.2e 1 -> 1.00e+00
%.2e 10 -> 1.00e+01
%.2e 100 -> 1.00e+02
%.2e 1000 -> 1.00e+03
%.2e 1500 -> 1.50e+03
%.2e 1590 -> 1.59e+03
%.2e 1598 -> 1.60e+03
%.2e 1598.7 -> 1.60e+03
%.2e 1598.76 -> 1.60e+03
%.2e 9999 -> 1.00e+04

-- omitted precision defaults to 6
%e 0 -> 0.000000e+00
%e 165 -> 1.650000e+02
%e 1234567 -> 1.234567e+06
%e 12345678 -> 1.234568e+07
%e 1.1 -> 1.100000e+00

-- alternate form always contains a decimal point.  This only makes
-- a difference when precision is 0.

%#.0e 0.01 -> 1.e-02
%#.0e 0.1 -> 1.e-01
%#.0e 1 -> 1.e+00
%#.0e 10 -> 1.e+01
%#.0e 100 -> 1.e+02
%#.0e 0.012 -> 1.e-02
%#.0e 0.12 -> 1.e-01
%#.0e 1.2 -> 1.e+00
%#.0e 12 -> 1.e+01
%#.0e 120 -> 1.e+02
%#.0e 123.456 -> 1.e+02
%#.0e 0.000123456 -> 1.e-04
%#.0e 123456000 -> 1.e+08
%#.0e 0.5 -> 5.e-01
%#.0e 1.4 -> 1.e+00
%#.0e 1.5 -> 2.e+00
%#.0e 1.6 -> 2.e+00
%#.0e 2.4999999 -> 2.e+00
%#.0e 2.5 -> 2.e+00
%#.0e 2.5000001 -> 3.e+00
%#.0e 3.499999999999 -> 3.e+00
%#.0e 3.5 -> 4.e+00
%#.0e 4.5 -> 4.e+00
%#.0e 5.5 -> 6.e+00
%#.0e 6.5 -> 6.e+00
%#.0e 7.5 -> 8.e+00
%#.0e 8.5 -> 8.e+00
%#.0e 9.4999 -> 9.e+00
%#.0e 9.5 -> 1.e+01
%#.0e 10.5 -> 1.e+01
%#.0e 14.999 -> 1.e+01
%#.0e 15 -> 2.e+01
%#.1e 123.4 -> 1.2e+02
%#.2e 0.0001357 -> 1.36e-04

-- 'g' code formatting.

-- zeros
%.0g 0 -> 0
%.1g 0 -> 0
%.2g 0 -> 0
%.3g 0 -> 0
%.4g 0 -> 0
%.10g 0 -> 0
%.50g 0 -> 0
%.100g 0 -> 0

-- precision 0 doesn't make a lot of sense for the 'g' code (what does
-- it mean to have no significant digits?); in practice, it's interpreted
-- as identical to precision 1
%.0g 1000 -> 1e+03
%.0g 100 -> 1e+02
%.0g 10 -> 1e+01
%.0g 1 -> 1
%.0g 0.1 -> 0.1
%.0g 0.01 -> 0.01
%.0g 1e-3 -> 0.001
%.0g 1e-4 -> 0.0001
%.0g 1e-5 -> 1e-05
%.0g 1e-6 -> 1e-06
%.0g 12 -> 1e+01
%.0g 120 -> 1e+02
%.0g 1.2 -> 1
%.0g 0.12 -> 0.1
%.0g 0.012 -> 0.01
%.0g 0.0012 -> 0.001
%.0g 0.00012 -> 0.0001
%.0g 0.000012 -> 1e-05
%.0g 0.0000012 -> 1e-06

-- precision 1 identical to precision 0
%.1g 1000 -> 1e+03
%.1g 100 -> 1e+02
%.1g 10 -> 1e+01
%.1g 1 -> 1
%.1g 0.1 -> 0.1
%.1g 0.01 -> 0.01
%.1g 1e-3 -> 0.001
%.1g 1e-4 -> 0.0001
%.1g 1e-5 -> 1e-05
%.1g 1e-6 -> 1e-06
%.1g 12 -> 1e+01
%.1g 120 -> 1e+02
%.1g 1.2 -> 1
%.1g 0.12 -> 0.1
%.1g 0.012 -> 0.01
%.1g 0.0012 -> 0.001
%.1g 0.00012 -> 0.0001
%.1g 0.000012 -> 1e-05
%.1g 0.0000012 -> 1e-06

-- precision 2
%.2g 1000 -> 1e+03
%.2g 100 -> 1e+02
%.2g 10 -> 10
%.2g 1 -> 1
%.2g 0.1 -> 0.1
%.2g 0.01 -> 0.01
%.2g 0.001 -> 0.001
%.2g 1e-4 -> 0.0001
%.2g 1e-5 -> 1e-05
%.2g 1e-6 -> 1e-06
%.2g 1234 -> 1.2e+03
%.2g 123 -> 1.2e+02
%.2g 12.3 -> 12
%.2g 1.23 -> 1.2
%.2g 0.123 -> 0.12
%.2g 0.0123 -> 0.012
%.2g 0.00123 -> 0.0012
%.2g 0.000123 -> 0.00012
%.2g 0.0000123 -> 1.2e-05

-- bad cases from http://bugs.python.org/issue9980
%.12g 38210.0 -> 38210
%.12g 37210.0 -> 37210
%.12g 36210.0 -> 36210

-- alternate g formatting:  always include decimal point and
-- exactly <precision> significant digits.
%#.0g 0 -> 0.
%#.1g 0 -> 0.
%#.2g 0 -> 0.0
%#.3g 0 -> 0.00
%#.4g 0 -> 0.000

%#.0g 0.2 -> 0.2
%#.1g 0.2 -> 0.2
%#.2g 0.2 -> 0.20
%#.3g 0.2 -> 0.200
%#.4g 0.2 -> 0.2000
%#.10g 0.2 -> 0.2000000000

%#.0g 2 -> 2.
%#.1g 2 -> 2.
%#.2g 2 -> 2.0
%#.3g 2 -> 2.00
%#.4g 2 -> 2.000

%#.0g 20 -> 2.e+01
%#.1g 20 -> 2.e+01
%#.2g 20 -> 20.
%#.3g 20 -> 20.0
%#.4g 20 -> 20.00

%#.0g 234.56 -> 2.e+02
%#.1g 234.56 -> 2.e+02
%#.2g 234.56 -> 2.3e+02
%#.3g 234.56 -> 235.
%#.4g 234.56 -> 234.6
%#.5g 234.56 -> 234.56
%#.6g 234.56 -> 234.560

-- repr formatting.  Result always includes decimal point and at
-- least one digit after the point, or an exponent.
%r 0 -> 0.0
%r 1 -> 1.0

%r 0.01 -> 0.01
%r 0.02 -> 0.02
%r 0.03 -> 0.03
%r 0.04 -> 0.04
%r 0.05 -> 0.05

-- values >= 1e16 get an exponent
%r 10 -> 10.0
%r 100 -> 100.0
%r 1e15 -> 1000000000000000.0
%r 9.999e15 -> 9999000000000000.0
%r 9999999999999998 -> 9999999999999998.0
%r 9999999999999999 -> 1e+16
%r 1e16 -> 1e+16
%r 1e17 -> 1e+17

-- as do values < 1e-4
%r 1e-3 -> 0.001
%r 1.001e-4 -> 0.0001001
%r 1.0000000000000001e-4 -> 0.0001
%r 1.000000000000001e-4 -> 0.0001000000000000001
%r 1.00000000001e-4 -> 0.000100000000001
%r 1.0000000001e-4 -> 0.00010000000001
%r 1e-4 -> 0.0001
%r 0.99999999999999999e-4 -> 0.0001
%r 0.9999999999999999e-4 -> 9.999999999999999e-05
%r 0.999999999999e-4 -> 9.99999999999e-05
%r 0.999e-4 -> 9.99e-05
%r 1e-5 -> 1e-05
"""


def pct(fmt: str, x: float) -> str:
    # fmt % x: a % format is a literal here, so each format the tests use is one
    if fmt == '%.0f':
        return '%.0f' % x
    if fmt == '%.1f':
        return '%.1f' % x
    if fmt == '%.2f':
        return '%.2f' % x
    if fmt == '%.3f':
        return '%.3f' % x
    if fmt == '%.50f':
        return '%.50f' % x
    if fmt == '%#.0f':
        return '%#.0f' % x
    if fmt == '%#.1f':
        return '%#.1f' % x
    if fmt == '%#.2f':
        return '%#.2f' % x
    if fmt == '%f':
        return '%f' % x
    if fmt == '%.0e':
        return '%.0e' % x
    if fmt == '%.1e':
        return '%.1e' % x
    if fmt == '%.2e':
        return '%.2e' % x
    if fmt == '%.10e':
        return '%.10e' % x
    if fmt == '%.50e':
        return '%.50e' % x
    if fmt == '%e':
        return '%e' % x
    if fmt == '%#.0e':
        return '%#.0e' % x
    if fmt == '%#.1e':
        return '%#.1e' % x
    if fmt == '%#.2e':
        return '%#.2e' % x
    if fmt == '%.0g':
        return '%.0g' % x
    if fmt == '%.1g':
        return '%.1g' % x
    if fmt == '%.2g':
        return '%.2g' % x
    if fmt == '%.3g':
        return '%.3g' % x
    if fmt == '%.4g':
        return '%.4g' % x
    if fmt == '%.10g':
        return '%.10g' % x
    if fmt == '%.50g':
        return '%.50g' % x
    if fmt == '%.100g':
        return '%.100g' % x
    if fmt == '%.12g':
        return '%.12g' % x
    if fmt == '%#.0g':
        return '%#.0g' % x
    if fmt == '%#.1g':
        return '%#.1g' % x
    if fmt == '%#.2g':
        return '%#.2g' % x
    if fmt == '%#.3g':
        return '%#.3g' % x
    if fmt == '%#.4g':
        return '%#.4g' % x
    if fmt == '%#.10g':
        return '%#.10g' % x
    if fmt == '%#.5g':
        return '%#.5g' % x
    if fmt == '%#.6g':
        return '%#.6g' % x
    if fmt == '%r':
        return '%r' % x
    if fmt == '%+e':
        return '%+e' % x
    if fmt == '% e':
        return '% e' % x
    if fmt == '%+f':
        return '%+f' % x
    if fmt == '% f':
        return '% f' % x
    if fmt == '%g':
        return '%g' % x
    if fmt == '%+g':
        return '%+g' % x
    if fmt == '% g':
        return '% g' % x
    if fmt == '%+.0e':
        return '%+.0e' % x
    if fmt == '% .0e':
        return '% .0e' % x
    if fmt == '%.6f':
        return '%.6f' % x
    if fmt == '%+.6f':
        return '%+.6f' % x
    if fmt == '% .6f':
        return '% .6f' % x
    if fmt == '%.20g':
        return '%.20g' % x
    if fmt == '%+.20g':
        return '%+.20g' % x
    if fmt == '% .20g':
        return '% .20g' % x
    if fmt == '%#e':
        return '%#e' % x
    if fmt == '%+#e':
        return '%+#e' % x
    if fmt == '% #e':
        return '% #e' % x
    if fmt == '%#f':
        return '%#f' % x
    if fmt == '%+#f':
        return '%+#f' % x
    if fmt == '% #f':
        return '% #f' % x
    if fmt == '%#g':
        return '%#g' % x
    if fmt == '%+#g':
        return '%+#g' % x
    if fmt == '% #g':
        return '% #g' % x
    if fmt == '%#.20e':
        return '%#.20e' % x
    if fmt == '%+#.20e':
        return '%+#.20e' % x
    if fmt == '% #.20e':
        return '% #.20e' % x
    if fmt == '%#.15f':
        return '%#.15f' % x
    if fmt == '%+#.15f':
        return '%+#.15f' % x
    if fmt == '% #.15f':
        return '% #.15f' % x
    if fmt == '%+#.3g':
        return '%+#.3g' % x
    if fmt == '% #.3g':
        return '% #.3g' % x
    assert False, fmt
    return ''


def format_raises(value: float, spec: str) -> None:
    # assertRaises(ValueError, format, value, spec)
    try:
        s = format(value, spec)
    except ValueError as e:
        print("format(%r, %r) ValueError: %s" % (value, spec, e))
    else:
        assert False, "expected ValueError, got %r" % s


def test_format() -> None:
    # these should be rewritten to use both format(x, spec) and
    # x.__format__(spec)

    check("format(0.0, 'f')", format(0.0, 'f'), '0.000000')

    # the default is 'g', except for empty format spec
    check("format(0.0, '')", format(0.0, ''), '0.0')
    check("format(0.01, '')", format(0.01, ''), '0.01')
    check("format(0.01, 'g')", format(0.01, 'g'), '0.01')

    # empty presentation type should format in the same way as str
    # (issue 5920)
    x = 100/7.
    check("format(x, '')", format(x, ''), str(x))
    check("format(x, '-')", format(x, '-'), str(x))
    check("format(x, '>')", format(x, '>'), str(x))
    check("format(x, '2')", format(x, '2'), str(x))

    check("format(1.0, 'f')", format(1.0, 'f'), '1.000000')

    check("format(-1.0, 'f')", format(-1.0, 'f'), '-1.000000')

    check("format( 1.0, ' f')", format( 1.0, ' f'), ' 1.000000')
    check("format(-1.0, ' f')", format(-1.0, ' f'), '-1.000000')
    check("format( 1.0, '+f')", format( 1.0, '+f'), '+1.000000')
    check("format(-1.0, '+f')", format(-1.0, '+f'), '-1.000000')

    # % formatting
    check("format(-1.0, '%')", format(-1.0, '%'), '-100.000000%')

    # conversion to string should fail
    format_raises(3.0, "s")

    # confirm format options expected to fail on floats, such as integer
    # presentation types
    for format_spec in 'sbcdoxX':
        format_raises(0.0, format_spec)
        format_raises(1.0, format_spec)
        format_raises(-1.0, format_spec)
        format_raises(1e100, format_spec)
        format_raises(-1e100, format_spec)
        format_raises(1e-100, format_spec)
        format_raises(-1e-100, format_spec)

    # issue 3382
    check("format(NAN, 'f')", format(NAN, 'f'), 'nan')
    check("format(NAN, 'F')", format(NAN, 'F'), 'NAN')
    check("format(INF, 'f')", format(INF, 'f'), 'inf')
    check("format(INF, 'F')", format(INF, 'F'), 'INF')


def test_format_testfile() -> None:
    n = 0
    for line in FORMAT_TESTCASES.splitlines():  # with open(format_testfile, ...)
        if line.startswith('--'):
            continue
        line = line.strip()
        if not line:
            continue

        lhs, rhs = [part.strip() for part in line.split('->')]  # map(str.strip, ...)
        fmt, arg = lhs.split()
        f = float(arg)
        assert pct(fmt, f) == rhs, (fmt, arg)
        assert pct(fmt, -f) == '-' + rhs, (fmt, arg)
        n += 2
        if fmt != '%r':
            fmt2 = fmt[1:]
            assert format(f, fmt2) == rhs, (fmt2, arg)
            assert format(-f, fmt2) == '-' + rhs, (fmt2, arg)
            n += 2
    print("test_format_testfile: %d formats; %%.50e of 1e-5: %s, %%#.6g of 234.56: %s"
          % (n, pct('%.50e', 1e-5), pct('%#.6g', 234.56)))


def test_issue5864() -> None:
    check("format(123.456, '.4')", format(123.456, '.4'), '123.5')
    check("format(1234.56, '.4')", format(1234.56, '.4'), '1.235e+03')
    check("format(12345.6, '.4')", format(12345.6, '.4'), '1.235e+04')


def test_issue35560() -> None:
    check("format(123.0, '00')", format(123.0, '00'), '123.0')
    check("format(123.34, '00f')", format(123.34, '00f'), '123.340000')
    check("format(123.34, '00e')", format(123.34, '00e'), '1.233400e+02')
    check("format(123.34, '00g')", format(123.34, '00g'), '123.34')
    check("format(123.34, '00.10f')", format(123.34, '00.10f'), '123.3400000000')
    check("format(123.34, '00.10e')", format(123.34, '00.10e'), '1.2334000000e+02')
    check("format(123.34, '00.10g')", format(123.34, '00.10g'), '123.34')
    check("format(123.34, '01f')", format(123.34, '01f'), '123.340000')

    check("format(-123.0, '00')", format(-123.0, '00'), '-123.0')
    check("format(-123.34, '00f')", format(-123.34, '00f'), '-123.340000')
    check("format(-123.34, '00e')", format(-123.34, '00e'), '-1.233400e+02')
    check("format(-123.34, '00g')", format(-123.34, '00g'), '-123.34')
    check("format(-123.34, '00.10f')", format(-123.34, '00.10f'), '-123.3400000000')
    check("format(-123.34, '00.10f')", format(-123.34, '00.10f'), '-123.3400000000')
    check("format(-123.34, '00.10e')", format(-123.34, '00.10e'), '-1.2334000000e+02')
    check("format(-123.34, '00.10g')", format(-123.34, '00.10g'), '-123.34')


# RoundTestCase
def test_inf_nan() -> None:
    try:
        round(INF)
    except OverflowError as e:
        print("round(INF) OverflowError:", e)
    else:
        assert False, "expected OverflowError"
    try:
        round(-INF)
    except OverflowError as e:
        print("round(-INF) OverflowError:", e)
    else:
        assert False, "expected OverflowError"
    try:
        round(NAN)
    except ValueError as e:
        print("round(NAN) ValueError:", e)
    else:
        assert False, "expected ValueError"


def test_inf_nan_ndigits() -> None:
    check("round(INF, 0)", round(INF, 0), INF)
    check("round(-INF, 0)", round(-INF, 0), -INF)
    check_true("math.isnan(round(NAN, 0))", math.isnan(round(NAN, 0)))


def test_large_n() -> None:
    for n in [324, 325, 400, 2**31-1, 2**31, 2**32]:  # and 2**100 upstream
        check("round(123.456, %d)" % n, round(123.456, n), 123.456)
        check("round(-123.456, %d)" % n, round(-123.456, n), -123.456)
        check("round(1e300, %d)" % n, round(1e300, n), 1e300)
        check("round(1e-320, %d)" % n, round(1e-320, n), 1e-320)
    check("round(1e150, 300)", round(1e150, 300), 1e150)
    check("round(1e300, 307)", round(1e300, 307), 1e300)
    check("round(-3.1415, 308)", round(-3.1415, 308), -3.1415)
    check("round(1e150, 309)", round(1e150, 309), 1e150)
    check("round(1.4e-315, 315)", round(1.4e-315, 315), 1e-315)


def test_small_n() -> None:
    for n in [-308, -309, -400, 1-2**31, -2**31, -2**31-1]:  # and -2**100 upstream
        assertFloatsAreIdentical("round(123.456, %d)" % n, round(123.456, n), 0.0)
        assertFloatsAreIdentical("round(-123.456, %d)" % n, round(-123.456, n), -0.0)
        assertFloatsAreIdentical("round(1e300, %d)" % n, round(1e300, n), 0.0)
        assertFloatsAreIdentical("round(1e-320, %d)" % n, round(1e-320, n), 0.0)


def test_overflow() -> None:
    try:
        round(1.6e308, -308)
    except OverflowError as e:
        print("round(1.6e308, -308) OverflowError:", e)
    else:
        assert False, "expected OverflowError"
    try:
        round(-1.7e308, -308)
    except OverflowError as e:
        print("round(-1.7e308, -308) OverflowError:", e)
    else:
        assert False, "expected OverflowError"


def test_previous_round_bugs() -> None:
    # particular cases that have occurred in bug reports
    check("round(562949953421312.5, 1)", round(562949953421312.5, 1),
                      562949953421312.5)
    check("round(56294995342131.5, 3)", round(56294995342131.5, 3),
                     56294995342131.5)
    # round-half-even
    check("round(25.0, -1)", round(25.0, -1), 20.0)
    check("round(35.0, -1)", round(35.0, -1), 40.0)
    check("round(45.0, -1)", round(45.0, -1), 40.0)
    check("round(55.0, -1)", round(55.0, -1), 60.0)
    check("round(65.0, -1)", round(65.0, -1), 60.0)
    check("round(75.0, -1)", round(75.0, -1), 80.0)
    check("round(85.0, -1)", round(85.0, -1), 80.0)
    check("round(95.0, -1)", round(95.0, -1), 100.0)


def test_matches_float_format() -> None:
    # round should give the same results as float formatting
    n = 0
    for i in range(500):
        x = i/1000.
        assert float(format(x, '.0f')) == round(x, 0), x
        assert float(format(x, '.1f')) == round(x, 1), x
        assert float(format(x, '.2f')) == round(x, 2), x
        assert float(format(x, '.3f')) == round(x, 3), x
        n += 4

    for i in range(5, 5000, 10):
        x = i/1000.
        assert float(format(x, '.0f')) == round(x, 0), x
        assert float(format(x, '.1f')) == round(x, 1), x
        assert float(format(x, '.2f')) == round(x, 2), x
        assert float(format(x, '.3f')) == round(x, 3), x
        n += 4

    for i in range(500):
        x = random.random()
        assert float(format(x, '.0f')) == round(x, 0), x
        assert float(format(x, '.1f')) == round(x, 1), x
        assert float(format(x, '.2f')) == round(x, 2), x
        assert float(format(x, '.3f')) == round(x, 3), x
        n += 4
    print("test_matches_float_format: %d roundings; round(0.125, 2) = %r, round(4.995, 2) = %r"
          % (n, round(0.125, 2), round(4.995, 2)))


def test_format_specials() -> None:
    # Test formatting of nans and infs.

    def test(fmt: str, value: float, expected: str) -> None:
        # Test with both % and format().
        print(fmt, repr(value), repr(pct(fmt, value)))
        assert pct(fmt, value) == expected, fmt  # fmt % value
        fmt = fmt[1:] # strip off the %
        assert format(value, fmt) == expected, fmt

    for fmt in ['%e', '%f', '%g', '%.0e', '%.6f', '%.20g',
                '%#e', '%#f', '%#g', '%#.20e', '%#.15f', '%#.3g']:
        pfmt = '%+' + fmt[1:]
        sfmt = '% ' + fmt[1:]
        test(fmt, INF, 'inf')
        test(fmt, -INF, '-inf')
        test(fmt, NAN, 'nan')
        test(fmt, -NAN, 'nan')
        # When asking for a sign, it's always provided. nans are
        #  always positive.
        test(pfmt, INF, '+inf')
        test(pfmt, -INF, '-inf')
        test(pfmt, NAN, '+nan')
        test(pfmt, -NAN, '+nan')
        # When using ' ' for a sign code, only infs can be negative.
        #  Others have a space.
        test(sfmt, INF, ' inf')
        test(sfmt, -INF, '-inf')
        test(sfmt, NAN, ' nan')
        test(sfmt, -NAN, ' nan')


def test_None_ndigits() -> None:
    for x in round(1.23), round(1.23, None):  # and round(1.23, ndigits=None) upstream
        check("round(1.23[, None])", x, 1)
        check("isinstance(x, int)", isinstance(x, int), True)
    for x in round(1.78), round(1.78, None):  # and round(1.78, ndigits=None) upstream
        check("round(1.78[, None])", x, 2)
        check("isinstance(x, int)", isinstance(x, int), True)


test_format()
test_format_testfile()
test_issue5864()
test_issue35560()
test_inf_nan()
test_inf_nan_ndigits()
test_large_n()
test_small_n()
test_overflow()
test_previous_round_bugs()
test_matches_float_format()
test_format_specials()
test_None_ndigits()
