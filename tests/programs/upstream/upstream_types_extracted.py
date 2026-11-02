# CPython 3.13.16 Lib/test/test_types.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 9ecf8e399e30e83794a1fafc34c5b990da2fa469c980e2f2157eeedc1b118d24),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: TypesTests.test_boolean_ops, TypesTests.test_comparisons,
#   TypesTests.test_float_constructor, TypesTests.test_floats, TypesTests.test_format_spec_errors,
#   TypesTests.test_numeric_types, TypesTests.test_strings, TypesTests.test_zero_division.
class TypesTests:

    def test_boolean_ops(self):
        if 0 or 0:
            raise AssertionError('0 or 0 is true instead of false')
        if 1 and 1:
            pass
        else:
            raise AssertionError('1 and 1 is false instead of true')
        if not 1:
            raise AssertionError('not 1 is true instead of false')

    def test_comparisons(self):
        if 0 < 1 <= 1 == 1 >= 1 > 0 != 1:
            pass
        else:
            raise AssertionError('int comparisons failed')
        if 0.0 < 1.0 <= 1.0 == 1.0 >= 1.0 > 0.0 != 1.0:
            pass
        else:
            raise AssertionError('float comparisons failed')
        if '' < 'a' <= 'a' == 'a' < 'abc' < 'abd' < 'b':
            pass
        else:
            raise AssertionError('string comparisons failed')
        if None is None:
            pass
        else:
            raise AssertionError('identity test failed')

    def test_float_constructor(self):
        try:
            float('')
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            float('5\x00')
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            float('5_5\x00')
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')

    def test_zero_division(self):
        try:
            5.0 / 0.0
        except ZeroDivisionError:
            pass
        else:
            raise AssertionError("5.0 / 0.0 didn't raise ZeroDivisionError")
        try:
            5.0 // 0.0
        except ZeroDivisionError:
            pass
        else:
            raise AssertionError("5.0 // 0.0 didn't raise ZeroDivisionError")
        try:
            5.0 % 0.0
        except ZeroDivisionError:
            pass
        else:
            raise AssertionError("5.0 % 0.0 didn't raise ZeroDivisionError")
        try:
            5 / 0
        except ZeroDivisionError:
            pass
        else:
            raise AssertionError("5 / 0 didn't raise ZeroDivisionError")
        try:
            5 // 0
        except ZeroDivisionError:
            pass
        else:
            raise AssertionError("5 // 0 didn't raise ZeroDivisionError")
        try:
            5 % 0
        except ZeroDivisionError:
            pass
        else:
            raise AssertionError("5 % 0 didn't raise ZeroDivisionError")

    def test_numeric_types(self):
        if 0 != 0.0 or 1 != 1.0 or -1 != -1.0:
            raise AssertionError('int/float value not equal')
        if int() != 0:
            raise AssertionError('int() does not return 0')
        if float() != 0.0:
            raise AssertionError('float() does not return 0.0')
        if int(1.9) == 1 == int(1.1) and int(-1.1) == -1 == int(-1.9):
            pass
        else:
            raise AssertionError('int() does not round properly')
        if float(1) == 1.0 and float(-1) == -1.0 and (float(0) == 0.0):
            pass
        else:
            raise AssertionError('float() does not work properly')

    def test_floats(self):
        if 12.0 + 24.0 != 36.0:
            raise AssertionError('float op')
        if 12.0 + -24.0 != -12.0:
            raise AssertionError('float op')
        if -12.0 + 24.0 != 12.0:
            raise AssertionError('float op')
        if -12.0 + -24.0 != -36.0:
            raise AssertionError('float op')
        if not 12.0 < 24.0:
            raise AssertionError('float op')
        if not -24.0 < -12.0:
            raise AssertionError('float op')

    def test_strings(self):
        if len('') != 0:
            raise AssertionError("len('')")
        if len('a') != 1:
            raise AssertionError("len('a')")
        if len('abcdef') != 6:
            raise AssertionError("len('abcdef')")
        if 'xyz' + 'abcde' != 'xyzabcde':
            raise AssertionError('string concatenation')
        if 'xyz' * 3 != 'xyzxyzxyz':
            raise AssertionError('string repetition *3')
        if 0 * 'abcde' != '':
            raise AssertionError('string repetition 0*')
        if min('abc') != 'a' or max('abc') != 'c':
            raise AssertionError('min/max string')
        if 'a' in 'abc' and 'b' in 'abc' and ('c' in 'abc') and ('d' not in 'abc'):
            pass
        else:
            raise AssertionError('in/not in string')
        x = 'x' * 103
        if '%s!' % x != x + '!':
            raise AssertionError('nasty string formatting bug')
        a = '0123456789'
        assert a[:] == a
        assert a[::2] == '02468'
        assert a[1::2] == '13579'
        assert a[::-1] == '9876543210'
        assert a[::-2] == '97531'
        assert a[3::-2] == '31'
        assert a[-100:100] == a
        assert a[100:-100:-1] == a[::-1]
        assert a[-100:100:2] == '02468'

    def test_format_spec_errors(self):
        try:
            format(0, '1' * 10000 + 'd')
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            format(0, '.' + '1' * 10000 + 'd')
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            format(0, '1' * 1000 + '.' + '1' * 10000 + 'd')
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        for code in 'xXobns':
            try:
                format(0, ',' + code)
            except ValueError:
                pass
            else:
                raise AssertionError('did not raise')


def _TypesTests__test_boolean_ops():
    t = TypesTests()
    t.test_boolean_ops()
    print('ok TypesTests.test_boolean_ops')


def _TypesTests__test_comparisons():
    t = TypesTests()
    t.test_comparisons()
    print('ok TypesTests.test_comparisons')


def _TypesTests__test_float_constructor():
    t = TypesTests()
    t.test_float_constructor()
    print('ok TypesTests.test_float_constructor')


def _TypesTests__test_floats():
    t = TypesTests()
    t.test_floats()
    print('ok TypesTests.test_floats')


def _TypesTests__test_format_spec_errors():
    t = TypesTests()
    t.test_format_spec_errors()
    print('ok TypesTests.test_format_spec_errors')


def _TypesTests__test_numeric_types():
    t = TypesTests()
    t.test_numeric_types()
    print('ok TypesTests.test_numeric_types')


def _TypesTests__test_strings():
    t = TypesTests()
    t.test_strings()
    print('ok TypesTests.test_strings')


def _TypesTests__test_zero_division():
    t = TypesTests()
    t.test_zero_division()
    print('ok TypesTests.test_zero_division')


_TypesTests__test_boolean_ops()
_TypesTests__test_comparisons()
_TypesTests__test_float_constructor()
_TypesTests__test_floats()
_TypesTests__test_format_spec_errors()
_TypesTests__test_numeric_types()
_TypesTests__test_strings()
_TypesTests__test_zero_division()
