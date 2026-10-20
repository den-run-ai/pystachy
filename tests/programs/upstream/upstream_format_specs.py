# Adapted from CPython 3.13.16 Lib/test/test_format.py, class FormatTest:
# test_g_format_has_no_trailing_zeros, test_with_two_commas_in_format_specifier,
# test_with_two_underscore_in_format_specifier,
# test_with_a_commas_and_an_underscore_in_format_specifier,
# test_with_an_underscore_and_a_comma_in_format_specifier, test_unicode_in_error_message,
# test_negative_zero and test_specifier_z_error, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) is eq(a, b), which
# prints a and asserts a == b; `with self.assertRaisesRegex(E, msg):` is a try statement that
# prints the exception (the message is printed, not matched, so the error_msg variables are
# left out where nothing else reads them). 54 of these methods' 60 assertions are adopted, all
# but these (test_format.py line numbers):
# EXCLUDED upstream cases:
# - test_negative_zero's complex numbers (rejected: "complex numbers are not supported") 620-623
# - test_specifier_z_error's "%z.1f" % 0 (a compile-time error here, with CPython's message
#   "unsupported format character 'z' (0x7a) at index 1": tests/errors/upstream/upstream_format_percent_z.py)
#   644 and b"%z.1f" % 0 (rejected: "unsupported operand type(s) for %: 'bytes' and 'int'")
#   646
# - testformat()/testcommon() and test_common_format, test_str_format, test_nul, test_non_ascii,
#   test_precision* (% formatting, which tests/programs/upstream/upstream_float_format.py and
#   tests/programs/upstream/upstream_int_format.py adopt from test_float.py and test_long.py), test_locale,
#   test_optimisations, test_bytes_and_bytearray_format, test_better_error_message_format
#   (complex, eval())
def eq(got, expected) -> None:
    print(repr(got))
    assert got == expected, (got, expected)


def test_g_format_has_no_trailing_zeros() -> None:
    eq("%.3g" % 1505.0, "1.5e+03")
    eq("%#.3g" % 1505.0, "1.50e+03")
    eq(format(1505.0, ".3g"), "1.5e+03")
    eq(format(1505.0, "#.3g"), "1.50e+03")
    eq(format(12300050.0, ".6g"), "1.23e+07")
    eq(format(12300050.0, "#.6g"), "1.23000e+07")


def test_with_two_commas_in_format_specifier() -> None:
    try:
        '{:,,}'.format(1)
    except ValueError as e:
        print(type(e).__name__ + ':', e)


def test_with_two_underscore_in_format_specifier() -> None:
    try:
        '{:__}'.format(1)
    except ValueError as e:
        print(type(e).__name__ + ':', e)


def test_with_a_commas_and_an_underscore_in_format_specifier() -> None:
    try:
        '{:,_}'.format(1)
    except ValueError as e:
        print(type(e).__name__ + ':', e)


def test_with_an_underscore_and_a_comma_in_format_specifier() -> None:
    try:
        '{:_,}'.format(1)
    except ValueError as e:
        print(type(e).__name__ + ':', e)


def test_unicode_in_error_message() -> None:
    try:
        "{a:%ЫйЯЧ}".format(a='a')
    except ValueError as e:
        print(type(e).__name__ + ':', e)


def test_negative_zero() -> None:
    eq(f"{-0.:.1f}", "-0.0")
    eq(f"{-.01:.1f}", "-0.0")
    eq(f"{-0:.1f}", "0.0")
    eq(f"{0.:z.1f}", "0.0")
    eq(f"{0.:z6.1f}", "   0.0")
    eq(f"{-1.:z6.1f}", "  -1.0")
    eq(f"{-0.:z.1f}", "0.0")
    eq(f"{.01:z.1f}", "0.0")
    eq(f"{-0:z.1f}", "0.0")
    eq(f"{-.01:z.1f}", "0.0")
    eq(f"{0.:z.2f}", "0.00")
    eq(f"{-0.:z.2f}", "0.00")
    eq(f"{.001:z.2f}", "0.00")
    eq(f"{-.001:z.2f}", "0.00")
    eq(f"{0.:z.1e}", "0.0e+00")
    eq(f"{-0.:z.1e}", "0.0e+00")
    eq(f"{0.:z.1E}", "0.0E+00")
    eq(f"{-0.:z.1E}", "0.0E+00")
    eq(f"{-0.001:z.2e}", "-1.00e-03")
    eq(f"{-0.001:z.2g}", "-0.001")
    eq(f"{-0.001:z.2%}", "-0.10%")
    eq(f"{-00000.000001:z.1f}", "0.0")
    eq(f"{-00000.:z.1f}", "0.0")
    eq(f"{-.0000000000:z.1f}", "0.0")
    eq(f"{-00000.000001:z.2f}", "0.00")
    eq(f"{-00000.:z.2f}", "0.00")
    eq(f"{-.0000000000:z.2f}", "0.00")
    eq(f"{.09:z.1f}", "0.1")
    eq(f"{-.09:z.1f}", "-0.1")
    eq(f"{-0.: z.0f}", " 0")
    eq(f"{-0.:+z.0f}", "+0")
    eq(f"{-0.:-z.0f}", "0")
    eq(f"{-1.: z.0f}", "-1")
    eq(f"{-1.:+z.0f}", "-1")
    eq(f"{-1.:-z.0f}", "-1")
    eq(f"{-0.:z>6.1f}", "zz-0.0")
    eq(f"{-0.:z>z6.1f}", "zzz0.0")
    eq(f"{-0.:x>z6.1f}", "xxx0.0")
    eq(f"{-0.:🖤>z6.1f}", "🖤🖤🖤0.0")


def test_specifier_z_error() -> None:
    try:
        f"{0:z+f}"  # wrong position
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        f"{0:fz}"  # wrong position
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        f"{0:zd}"  # can't apply to int presentation type
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        f"{'x':zs}"  # can't apply to string
    except ValueError as e:
        print(type(e).__name__ + ':', e)


test_g_format_has_no_trailing_zeros()
test_with_two_commas_in_format_specifier()
test_with_two_underscore_in_format_specifier()
test_with_a_commas_and_an_underscore_in_format_specifier()
test_with_an_underscore_and_a_comma_in_format_specifier()
test_unicode_in_error_message()
test_negative_zero()
test_specifier_z_error()
