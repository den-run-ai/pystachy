# Adapted from CPython 3.13.16 Lib/test/test_string.py, class ModuleTest: test_basic_formatter,
# test_format_keyword_arguments, test_auto_numbering, test_conversion_specifiers and
# test_override_convert_field, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# string.Formatter is lib/string.py's (adapted, with _string's parsers in
# lib/_pystachy_string.py). Each test method becomes a function of the same name;
# assertEqual(a, b) is eq(a, b), which prints a and asserts a == b; assertRaises(E, f, *args),
# assertRaisesRegex and `with self.assertRaises(E):` are try statements that print the exception
# (the regex is not matched). test_override_convert_field's XFormatter is a module class. 22 of
# these methods' 44 assertions are adopted, all but these (test_string.py line numbers):
# EXCLUDED upstream cases:
# - fmt.format() and string.Formatter.format() without a format string (compile-time errors
#   here, "Formatter.format() missing 1 required positional argument: 'format_string'" as
#   CPython words it; "Formatter.format() is a method of its objects: calling it through the
#   class is not supported") 39 40 51 (tests/errors/upstream/upstream_string_formatter_no_format_string.py)
# - test_auto_numbering's arguments of different types (rejected inside lib/string.py:
#   "get_value() returns both str | None and int (each function has one return type)") 58 64
# - test_name_lookup and test_index_lookup: Formatter looks up no attributes or items of
#   arguments (ValueError: Pystachy's string.Formatter does not look up attributes of
#   arguments: '0.lumber'; documented, tests/deviations/lib_string_formatter_fields.py) 91 92 98
#   99 101; test_override_get_value (rejected: "inheritance with generic class templates is not
#   supported: annotate __init__ parameters") 121; test_override_format_field (a lambda as an
#   argument: "printing a function, or comparing containers of functions, is not supported")
#   130; test_override_parse (a generator, "'yield' is not supported") 158;
#   test_check_unused_args' set of keyword names updated with ints (rejected: "set.update() of
#   list[int] for a set of str is not supported: a set holds elements of one type") 174-180;
#   test_vformat_recursion_limit (dict(i=100), #516, and _vformat()) 186 188
# - test_attrs, test_capwords and TestTemplate: tests/programs/library/lib_string.py checks the constants,
#   capwords() and Template after these tests
import string


def eq(got, expected) -> None:
    print(repr(got))
    assert got == expected, (got, expected)


def test_basic_formatter() -> None:
    fmt = string.Formatter()
    eq(fmt.format("foo"), "foo")
    eq(fmt.format("foo{0}", "bar"), "foobar")
    eq(fmt.format("foo{1}{0}-{1}", "bar", 6), "foo6bar-6")


def test_format_keyword_arguments() -> None:
    fmt = string.Formatter()
    eq(fmt.format("-{arg}-", arg='test'), '-test-')
    try:
        fmt.format("-{arg}-")
    except KeyError as e:
        print(type(e).__name__ + ':', e)
    eq(fmt.format("-{self}-", self='test'), '-test-')
    try:
        fmt.format("-{self}-")
    except KeyError as e:
        print(type(e).__name__ + ':', e)
    eq(fmt.format("-{format_string}-", format_string='test'), '-test-')
    try:
        fmt.format("-{format_string}-")
    except KeyError as e:
        print(type(e).__name__ + ':', e)


def test_auto_numbering() -> None:
    fmt = string.Formatter()
    eq(fmt.format('foo{}{}', 'bar', 6), 'foo{}{}'.format('bar', 6))
    eq(fmt.format('{:^{}}', 'bar', 6), '{:^{}}'.format('bar', 6))
    eq(fmt.format('{:^{}} {}', 'bar', 6, 'X'), '{:^{}} {}'.format('bar', 6, 'X'))
    try:
        fmt.format('foo{1}{}', 'bar', 6)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        fmt.format('foo{}{1}', 'bar', 6)
    except ValueError as e:
        print(type(e).__name__ + ':', e)


def test_conversion_specifiers() -> None:
    fmt = string.Formatter()
    eq(fmt.format("-{arg!r}-", arg='test'), "-'test'-")
    eq(fmt.format("{0!s}", 'test'), 'test')
    try:
        fmt.format("{0!h}", 'test')
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    eq(fmt.format("{0!a}", 42), '42')
    eq(fmt.format("{0!a}",  string.ascii_letters), "'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'")
    eq(fmt.format("{0!a}",  chr(255)), "'\\xff'")
    eq(fmt.format("{0!a}",  chr(256)), "'\\u0100'")


class XFormatter(string.Formatter):
    def convert_field(self, value, conversion):
        if conversion == 'x':
            return None
        return super().convert_field(value, conversion)


def test_override_convert_field() -> None:
    fmt = XFormatter()
    eq(fmt.format("{0!r}:{0!x}", 'foo', 'foo'), "'foo':None")


test_basic_formatter()
test_format_keyword_arguments()
test_auto_numbering()
test_conversion_specifiers()
test_override_convert_field()
