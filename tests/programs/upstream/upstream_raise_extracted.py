# CPython 3.13.16 Lib/test/test_raise.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 ff1037ebdfb6b1f8900041bbb4b39d26441ed25b13783368169cda6e57bc8647),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: TestRaise.test_assert_with_tuple_arg, TestRaise.test_except_reraise,
#   TestRaise.test_finally_reraise, TestRaise.test_invalid_reraise, TestRaise.test_nested_reraise,
#   TestRaise.test_reraise, TestRaise.test_with_reraise1, TestRaise.test_with_reraise2,
#   TestRaise.test_yield_reraise, TestCause.test_class_cause, TestCause.test_instance_cause,
#   TestCause.test_invalid_cause.
"""Tests for the raise statement."""

class Context:

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        return True

class TestRaise:

    def test_invalid_reraise(self):
        try:
            raise
        except RuntimeError as e:
            assert 'No active exception' in str(e)
        else:
            raise AssertionError('No exception raised')

    def test_reraise(self):
        try:
            try:
                raise IndexError()
            except IndexError as e:
                exc1 = e
                raise
        except IndexError as exc2:
            assert exc1 is exc2
        else:
            raise AssertionError('No exception raised')

    def test_except_reraise(self):

        def reraise():
            try:
                raise TypeError('foo')
            except:
                try:
                    raise KeyError('caught')
                except KeyError:
                    pass
                raise
        try:
            reraise()
        except TypeError:
            pass
        else:
            raise AssertionError('did not raise')

    def test_finally_reraise(self):

        def reraise():
            try:
                raise TypeError('foo')
            except:
                try:
                    raise KeyError('caught')
                finally:
                    raise
        try:
            reraise()
        except KeyError:
            pass
        else:
            raise AssertionError('did not raise')

    def test_nested_reraise(self):

        def nested_reraise():
            raise

        def reraise():
            try:
                raise TypeError('foo')
            except:
                nested_reraise()
        try:
            reraise()
        except TypeError:
            pass
        else:
            raise AssertionError('did not raise')

    def test_with_reraise1(self):

        def reraise():
            try:
                raise TypeError('foo')
            except:
                with Context():
                    pass
                raise
        try:
            reraise()
        except TypeError:
            pass
        else:
            raise AssertionError('did not raise')

    def test_with_reraise2(self):

        def reraise():
            try:
                raise TypeError('foo')
            except:
                with Context():
                    raise KeyError('caught')
                raise
        try:
            reraise()
        except TypeError:
            pass
        else:
            raise AssertionError('did not raise')

    def test_yield_reraise(self):

        def reraise():
            try:
                raise TypeError('foo')
            except:
                yield 1
                raise
        g = reraise()
        next(g)
        try:
            (lambda: next(g))()
        except TypeError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            (lambda: next(g))()
        except StopIteration:
            pass
        else:
            raise AssertionError('did not raise')

    def test_assert_with_tuple_arg(self):
        try:
            assert False, (3,)
        except AssertionError as e:
            assert str(e) == '(3,)'

class TestCause:

    def test_invalid_cause(self):
        try:
            raise IndexError from 5
        except TypeError as e:
            assert 'exception cause' in str(e)
        else:
            raise AssertionError('No exception raised')

    def test_class_cause(self):
        try:
            raise IndexError from KeyError
        except IndexError as e:
            assert isinstance(e.__cause__, KeyError)
        else:
            raise AssertionError('No exception raised')

    def test_instance_cause(self):
        cause = KeyError()
        try:
            raise IndexError from cause
        except IndexError as e:
            assert e.__cause__ is cause
        else:
            raise AssertionError('No exception raised')


def _TestRaise__test_assert_with_tuple_arg():
    t = TestRaise()
    t.test_assert_with_tuple_arg()
    print('ok TestRaise.test_assert_with_tuple_arg')


def _TestRaise__test_except_reraise():
    t = TestRaise()
    t.test_except_reraise()
    print('ok TestRaise.test_except_reraise')


def _TestRaise__test_finally_reraise():
    t = TestRaise()
    t.test_finally_reraise()
    print('ok TestRaise.test_finally_reraise')


def _TestRaise__test_invalid_reraise():
    t = TestRaise()
    t.test_invalid_reraise()
    print('ok TestRaise.test_invalid_reraise')


def _TestRaise__test_nested_reraise():
    t = TestRaise()
    t.test_nested_reraise()
    print('ok TestRaise.test_nested_reraise')


def _TestRaise__test_reraise():
    t = TestRaise()
    t.test_reraise()
    print('ok TestRaise.test_reraise')


def _TestRaise__test_with_reraise1():
    t = TestRaise()
    t.test_with_reraise1()
    print('ok TestRaise.test_with_reraise1')


def _TestRaise__test_with_reraise2():
    t = TestRaise()
    t.test_with_reraise2()
    print('ok TestRaise.test_with_reraise2')


def _TestRaise__test_yield_reraise():
    t = TestRaise()
    t.test_yield_reraise()
    print('ok TestRaise.test_yield_reraise')


def _TestCause__test_class_cause():
    t = TestCause()
    t.test_class_cause()
    print('ok TestCause.test_class_cause')


def _TestCause__test_instance_cause():
    t = TestCause()
    t.test_instance_cause()
    print('ok TestCause.test_instance_cause')


def _TestCause__test_invalid_cause():
    t = TestCause()
    t.test_invalid_cause()
    print('ok TestCause.test_invalid_cause')


_TestRaise__test_assert_with_tuple_arg()
_TestRaise__test_except_reraise()
_TestRaise__test_finally_reraise()
_TestRaise__test_invalid_reraise()
_TestRaise__test_nested_reraise()
_TestRaise__test_reraise()
_TestRaise__test_with_reraise1()
_TestRaise__test_with_reraise2()
_TestRaise__test_yield_reraise()
_TestCause__test_class_cause()
_TestCause__test_instance_cause()
_TestCause__test_invalid_cause()
