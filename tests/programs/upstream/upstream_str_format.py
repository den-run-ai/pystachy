# Adapted from CPython 3.13.16 Lib/test/test_str.py, class StrTest: test_format, test_format_map
# and test_format_auto_numbering, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name (test_format is test_format and
# test_format_2, its statements in upstream's order); its local classes are module classes.
# assertEqual(a, b) is eq(a, b), which prints a and asserts a == b; assertRaises(E, f, *args)
# is a try statement that calls f(*args) and prints the exception; the regex of
# assertRaisesRegex is not matched (the message is printed). format_map({}) is of `empty`, an
# annotated empty dict. 203 of the methods' 241 assertions are adopted, all but these
# (Lib/test/test_str.py line numbers):
# EXCLUDED upstream cases:
# - complex numbers (rejected: "complex numbers are not supported"): 1239-1242, 1334-1344
# - lists and dicts whose items differ, or empty and None displays as arguments (rejected:
#   "expected str, got list[str]" 1189, "expected str, got list[D[str]]" 1190, "cannot infer the
#   type of an empty dict" 1266, "... of an empty list" 1267 1312 and test_format_map 1453,
#   "... of a list of None" 1348 1349); dict(name='Fred') 1086 (rejected: "keyword argument
#   'name' of dict() is not supported", #516)
# - E (no __format__, rejected: "unsupported format string passed to E.__format__") 1273 1274;
#   G's object.__format__(self, spec) fallback (rejected: "'fn[b:object]' has no method
#   '__format__'") 1270 1275; M and N (`__str__ = None`, `__format__ = None`, rejected: "cannot
#   infer the type of class attribute '__str__'") 1393-1399; I(datetime.date), J(int) and
#   test_format_map's Mapping(dict) (rejected: "unsupported base class: single inheritance
#   requires a previously declared ordinary class or a supported exception class") 1277 1283
#   1415 1416
# - str.format() of a format string computed at run time (rejected: "str.format() of a format
#   string computed at run time is not supported ...") 1330 1331 ("{" + big + "}");
#   '{0[{1}]}'.format('abcdefg', 4) 1352 (rejected: "expected int, got str")
# - test_format_map's ''.format_map() and 'a'.format_map() without an argument (a compile-time
#   error with CPython's message, "str.format_map() takes exactly one argument (0 given)":
#   tests/errors/upstream/upstream_str_format_map_no_argument.py) 1434 1435
# - test_format_huge_precision, test_format_huge_width, test_format_huge_item_number (sizes
#   past 2**63, documented), test_formatting* (% formatting), test_format_subclass,
#   test_formatter_parser and test_formatter_field_name_split (_string)
# (an empty dict display that nothing types: format_map({}))
empty: dict[str, str] = {}


def eq(got, expected) -> None:
    print(repr(got))
    assert got == expected, (got, expected)


class C:
    def __init__(self, x=100):
        self._x = x
    def __format__(self, spec):
        return spec


class D:
    def __init__(self, x):
        self.x = x
    def __format__(self, spec):
        return str(self.x)


class F:
    def __init__(self, x):
        self.x = x
    def __repr__(self):
        return 'F(' + self.x + ')'


class G:
    def __init__(self, x):
        self.x = x
    def __str__(self):
        return "string is " + self.x
    def __format__(self, format_spec):
        if format_spec == 'd':
            return 'G(' + self.x + ')'
        return object.__format__(self, format_spec)


def test_format() -> None:
    eq(''.format(), '')
    eq('a'.format(), 'a')
    eq('ab'.format(), 'ab')
    eq('a{{'.format(), 'a{')
    eq('a}}'.format(), 'a}')
    eq('{{b'.format(), '{b')
    eq('}}b'.format(), '}b')
    eq('a{{b'.format(), 'a{b')
    import datetime
    eq("My name is {0}".format('Fred'), "My name is Fred")
    eq("My name is {0} :-{{}}".format('Fred'), "My name is Fred :-{}")
    d = datetime.date(2007, 8, 18)
    eq("The year is {0.year}".format(d), "The year is 2007")
    eq(''.format(), '')
    eq('abc'.format(), 'abc')
    eq('{0}'.format('abc'), 'abc')
    eq('{0:}'.format('abc'), 'abc')
    eq('X{0}'.format('abc'), 'Xabc')
    eq('{0}X'.format('abc'), 'abcX')
    eq('X{0}Y'.format('abc'), 'XabcY')
    eq('{1}'.format(1, 'abc'), 'abc')
    eq('X{1}'.format(1, 'abc'), 'Xabc')
    eq('{1}X'.format(1, 'abc'), 'abcX')
    eq('X{1}Y'.format(1, 'abc'), 'XabcY')
    eq('{0}'.format(-15), '-15')
    eq('{0}{1}'.format(-15, 'abc'), '-15abc')
    eq('{0}X{1}'.format(-15, 'abc'), '-15Xabc')
    eq('{{'.format(), '{')
    eq('}}'.format(), '}')
    eq('{{}}'.format(), '{}')
    eq('{{x}}'.format(), '{x}')
    eq('{{{0}}}'.format(123), '{123}')
    eq('{{{{0}}}}'.format(), '{{0}}')
    eq('}}{{'.format(), '}{')
    eq('}}x{{'.format(), '}x{')
    eq("{0[foo-bar]}".format({'foo-bar':'baz'}), 'baz')
    eq("{0[foo bar]}".format({'foo bar':'baz'}), 'baz')
    eq("{0[ ]}".format({' ':3}), '3')
    eq('{foo._x}'.format(foo=C(20)), '20')
    eq('{1}{0}'.format(D(10), D(20)), '2010')
    eq('{0._x.x}'.format(C(D('abc'))), 'abc')
    eq('{0[0]}'.format(['abc', 'def']), 'abc')
    eq('{0[1]}'.format(['abc', 'def']), 'def')
    eq('{0:.3s}'.format('abc'), 'abc')
    eq('{0:.3s}'.format('ab'), 'ab')
    eq('{0:.3s}'.format('abcdef'), 'abc')
    eq('{0:.0s}'.format('abcdef'), '')
    eq('{0:3.3s}'.format('abc'), 'abc')
    eq('{0:2.3s}'.format('abc'), 'abc')
    eq('{0:2.2s}'.format('abc'), 'ab')
    eq('{0:3.2s}'.format('abc'), 'ab ')
    eq('{0:x<0s}'.format('result'), 'result')
    eq('{0:x<5s}'.format('result'), 'result')
    eq('{0:x<6s}'.format('result'), 'result')
    eq('{0:x<7s}'.format('result'), 'resultx')
    eq('{0:x<8s}'.format('result'), 'resultxx')
    eq('{0: <7s}'.format('result'), 'result ')
    eq('{0:<7s}'.format('result'), 'result ')
    eq('{0:>7s}'.format('result'), ' result')
    eq('{0:>8s}'.format('result'), '  result')
    eq('{0:^8s}'.format('result'), ' result ')
    eq('{0:^9s}'.format('result'), ' result  ')
    eq('{0:^10s}'.format('result'), '  result  ')
    eq('{0:8s}'.format('result'), 'result  ')
    eq('{0:0s}'.format('result'), 'result')
    eq('{0:08s}'.format('result'), 'result00')
    eq('{0:<08s}'.format('result'), 'result00')
    eq('{0:>08s}'.format('result'), '00result')
    eq('{0:^08s}'.format('result'), '0result0')
    eq('{0:10000}'.format('a'), 'a' + ' ' * 9999)
    eq('{0:10000}'.format(''), ' ' * 10000)
    eq('{0:10000000}'.format(''), ' ' * 10000000)
    eq('{0:\x00<6s}'.format('foo'), 'foo\x00\x00\x00')
    eq('{0:\x01<6s}'.format('foo'), 'foo\x01\x01\x01')
    eq('{0:\x00^6s}'.format('foo'), '\x00foo\x00\x00')
    eq('{0:^6s}'.format('foo'), ' foo  ')
    eq('{0:\x00<6}'.format(3), '3\x00\x00\x00\x00\x00')
    eq('{0:\x01<6}'.format(3), '3\x01\x01\x01\x01\x01')
    eq('{0:\x00^6}'.format(3), '\x00\x003\x00\x00\x00')
    eq('{0:<6}'.format(3), '3     ')
    eq('{0:\x00<6}'.format(3.25), '3.25\x00\x00')
    eq('{0:\x01<6}'.format(3.25), '3.25\x01\x01')
    eq('{0:\x00^6}'.format(3.25), '\x003.25\x00')
    eq('{0:^6}'.format(3.25), ' 3.25 ')
    eq('{0:abc}'.format(C()), 'abc')
    eq('{0!s}'.format('Hello'), 'Hello')
    eq('{0!s:}'.format('Hello'), 'Hello')
    eq('{0!s:15}'.format('Hello'), 'Hello          ')
    eq('{0!s:15s}'.format('Hello'), 'Hello          ')
    eq('{0!r}'.format('Hello'), "'Hello'")
    eq('{0!r:}'.format('Hello'), "'Hello'")
    eq('{0!r}'.format(F('Hello')), 'F(Hello)')
    eq('{0!r}'.format('\u0378'), "'\\u0378'")
    eq('{0!r}'.format('\u0374'), "'\u0374'")
    eq('{0!r}'.format(F('\u0374')), 'F(\u0374)')
    eq('{0!a}'.format('Hello'), "'Hello'")
    eq('{0!a}'.format('\u0378'), "'\\u0378'")
    eq('{0!a}'.format('\u0374'), "'\\u0374'")
    eq('{0!a:}'.format('Hello'), "'Hello'")
    eq('{0!a}'.format(F('Hello')), 'F(Hello)')
    eq('{0!a}'.format(F('\u0374')), 'F(\\u0374)')
    eq('{0}'.format([1]), '[1]')
    eq('{0!s}'.format(G('data')), 'string is data')


def test_format_2() -> None:
    import datetime
    d = datetime.date(2007, 8, 18)
    eq('{0:}'.format('a'), 'a')
    eq("{0:.{1}}".format('hello world', 5), 'hello')
    eq("{0:.{1}s}".format('hello world', 5), 'hello')
    eq("{0:.{precision}s}".format('hello world', precision=5), 'hello')
    eq("{0:{width}.{precision}s}".format('hello world', width=10, precision=5), 'hello     ')
    eq("{0:{width}.{precision}s}".format('hello world', width='10', precision='5'), 'hello     ')
    try:
        '{'.format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '}'.format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        'a{'.format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        'a}'.format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{a'.format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '}a'.format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{0}'.format()
    except IndexError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{1}'.format('abc')
    except IndexError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{x}'.format()
    except KeyError as e:
        print(type(e).__name__ + ':', e)
    try:
        "}{".format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "abc{0:{}".format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0".format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0.}".format()
    except IndexError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0.}".format(0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0[}".format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0]}".format()
    except KeyError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0.[]}".format(0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0..foo}".format(0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0[0}".format(0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0[0:foo}".format(0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{c]}".format()
    except KeyError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{{ {{{0}}".format(0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0}}".format(0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{foo}".format(bar=3)
    except KeyError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0!x}".format(3)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0!}".format(0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0!rs}".format(0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{!}".format()
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{:}".format()
    except IndexError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{:s}".format()
    except IndexError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{}".format()
    except IndexError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{0:x}'.format(1.0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{0:X}'.format(1.0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{0:o}'.format(1.0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{0:u}'.format(1.0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{0:i}'.format(1.0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{0:d}'.format(1.0)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0:{1:{2}}}".format('abc', 's', '')
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0:{1:{2:{3:{4:{5:{6}}}}}}}".format(0, 1, 2, 3, 4, 5, 6, 7)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0:-s}".format('')
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        format("", "-")
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{: }".format('')
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{0:=s}".format('')
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        format('', '#')
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        format('', '#20')
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    eq("{0:s}{1:s}".format("ABC", "\u0410\u0411\u0412"), 'ABC\u0410\u0411\u0412')
    eq("{0:.3s}".format("ABC\u0410\u0411\u0412"), 'ABC')
    eq("{0:.0s}".format("ABC\u0410\u0411\u0412"), '')
    eq("{[{}]}".format({"{}": 5}), "5")
    eq("{[{}]}".format({"{}" : "a"}), "a")
    eq("{[{]}".format({"{" : "a"}), "a")
    eq("{[}]}".format({"}" : "a"}), "a")
    eq("{[[]}".format({"[" : "a"}), "a")
    eq("{[!]}".format({"!" : "a"}), "a")
    try:
        "{a{}b}".format(42)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{a{b}".format(42)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        "{[}".format(42)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    eq("0x{:0{:d}X}".format(0x0,16), "0x0000000000000000")


class InternalMapping:
    def __init__(self):
        self.mapping = {'a': 'hello'}
    def __getitem__(self, key):
        return self.mapping[key]


class BadMapping:
    def __getitem__(self, key):
        return 1/0


def test_format_map() -> None:
    eq(''.format_map(empty), '')
    eq('a'.format_map(empty), 'a')
    eq('ab'.format_map(empty), 'ab')
    eq('a{{'.format_map(empty), 'a{')
    eq('a}}'.format_map(empty), 'a}')
    eq('{{b'.format_map(empty), '{b')
    eq('}}b'.format_map(empty), '}b')
    eq('a{{b'.format_map(empty), 'a{b')
    eq('{a}'.format_map(InternalMapping()), 'hello')
    eq('{foo._x}'.format_map({'foo': C(20)}), '20')
    try:
        '{'.format_map(empty)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '}'.format_map(empty)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        'a{'.format_map(empty)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        'a}'.format_map(empty)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{a'.format_map(empty)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '}a'.format_map(empty)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{}'.format_map({'a' : 2})
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{}'.format_map('a')
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{a} {}'.format_map({"a" : 2, "b" : 1})
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{a}'.format_map(empty)
    except KeyError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{a}'.format_map(BadMapping())
    except ZeroDivisionError as e:
        print(type(e).__name__ + ':', e)


def test_format_auto_numbering() -> None:
    eq('{}'.format(10), '10')
    eq('{:5}'.format('s'), 's    ')
    eq('{!r}'.format('s'), "'s'")
    eq('{._x}'.format(C(10)), '10')
    eq('{[1]}'.format([1, 2]), '2')
    eq('{[a]}'.format({'a':4, 'b':2}), '4')
    eq('a{}b{}c'.format(0, 1), 'a0b1c')
    eq('a{:{}}b'.format('x', '^10'), 'a    x     b')
    eq('a{:{}x}b'.format(20, '#'), 'a0x14b')
    try:
        '{}{1}'.format(1, 2)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{1}{}'.format(1, 2)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{:{1}}'.format(1, 2)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        '{0:{}}'.format(1, 2)
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    eq('{f}{}'.format(4, f='test'), 'test4')
    eq('{}{f}'.format(4, f='test'), '4test')
    eq('{:{f}}{g}{}'.format(1, 3, g='g', f=2), ' 1g3')
    eq('{f:{}}{}{g}'.format(2, 4, f=1, g='g'), ' 14g')


test_format()
test_format_2()
test_format_map()
test_format_auto_numbering()
