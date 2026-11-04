# CPython 3.13.16 Lib/test/test_copy.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 e137a3f2b5d5bbfe42eba2e1923d84de15a2e5ce8e6e330b88c88672982db016).
# Mechanically extracted with tools/cpython_test_methods.py (tests/upstream/core-sweep.md).
"""Unit tests for the copy module."""
import copy
import weakref

class TestCopy:

    def test_exceptions(self):
        assert copy.Error is copy.error
        assert issubclass(copy.Error, Exception)

    def test_copy_basic(self):
        x = 42
        y = copy.copy(x)
        assert x == y

    def test_copy_list(self):
        x = [1, 2, 3]
        y = copy.copy(x)
        assert y == x
        assert y is not x
        x = []
        y = copy.copy(x)
        assert y == x
        assert y is not x

    def test_copy_dict(self):
        x = {'foo': 1, 'bar': 2}
        y = copy.copy(x)
        assert y == x
        assert y is not x
        x = {}
        y = copy.copy(x)
        assert y == x
        assert y is not x

    def test_copy_set(self):
        x = {1, 2, 3}
        y = copy.copy(x)
        assert y == x
        assert y is not x
        x = set()
        y = copy.copy(x)
        assert y == x
        assert y is not x

    def test_copy_frozenset(self):
        x = frozenset({1, 2, 3})
        assert copy.copy(x) is x
        x = frozenset()
        assert copy.copy(x) is x

    def test_deepcopy_basic(self):
        x = 42
        y = copy.deepcopy(x)
        assert y == x

    def test_deepcopy_empty_tuple(self):
        x = ()
        y = copy.deepcopy(x)
        assert x is y

    def test_deepcopy_tuple(self):
        x = ([1, 2], 3)
        y = copy.deepcopy(x)
        assert y == x
        assert x is not y
        assert x[0] is not y[0]

    def test_deepcopy_tuple_of_immutables(self):
        x = ((1, 2), 3)
        y = copy.deepcopy(x)
        assert x is y

    def test_copy_function(self):
        assert copy.copy(global_foo) == global_foo

        def foo(x, y):
            return x + y
        assert copy.copy(foo) == foo
        bar = lambda: None
        assert copy.copy(bar) == bar

    def test_deepcopy_function(self):
        assert copy.deepcopy(global_foo) == global_foo

        def foo(x, y):
            return x + y
        assert copy.deepcopy(foo) == foo
        bar = lambda: None
        assert copy.deepcopy(bar) == bar

    def _check_weakref(self, _copy):

        class C(object):
            pass
        obj = C()
        x = weakref.ref(obj)
        y = _copy(x)
        assert y is x
        del obj
        y = _copy(x)
        assert y is x

    def _check_copy_weakdict(self, _dicttype):

        class C(object):
            pass
        a, b, c, d = [C() for i in range(4)]
        u = _dicttype()
        u[a] = b
        u[c] = d
        v = copy.copy(u)
        assert v is not u
        assert v == u
        assert v[a] == b
        assert v[c] == d
        assert len(v) == 2
        del c, d
        support.gc_collect()
        assert len(v) == 1
        x, y = (C(), C())
        v[x] = y
        assert x not in u

def global_foo(x, y):
    return x + y


def _TestCopy__test_copy_basic():
    t = TestCopy()
    t.test_copy_basic()
    print('ok TestCopy.test_copy_basic')


def _TestCopy__test_copy_dict():
    t = TestCopy()
    t.test_copy_dict()
    print('ok TestCopy.test_copy_dict')


def _TestCopy__test_copy_frozenset():
    t = TestCopy()
    t.test_copy_frozenset()
    print('ok TestCopy.test_copy_frozenset')


def _TestCopy__test_copy_function():
    t = TestCopy()
    t.test_copy_function()
    print('ok TestCopy.test_copy_function')


def _TestCopy__test_copy_list():
    t = TestCopy()
    t.test_copy_list()
    print('ok TestCopy.test_copy_list')


def _TestCopy__test_copy_set():
    t = TestCopy()
    t.test_copy_set()
    print('ok TestCopy.test_copy_set')


def _TestCopy__test_deepcopy_basic():
    t = TestCopy()
    t.test_deepcopy_basic()
    print('ok TestCopy.test_deepcopy_basic')


def _TestCopy__test_deepcopy_empty_tuple():
    t = TestCopy()
    t.test_deepcopy_empty_tuple()
    print('ok TestCopy.test_deepcopy_empty_tuple')


def _TestCopy__test_deepcopy_function():
    t = TestCopy()
    t.test_deepcopy_function()
    print('ok TestCopy.test_deepcopy_function')


def _TestCopy__test_deepcopy_tuple():
    t = TestCopy()
    t.test_deepcopy_tuple()
    print('ok TestCopy.test_deepcopy_tuple')


def _TestCopy__test_deepcopy_tuple_of_immutables():
    t = TestCopy()
    t.test_deepcopy_tuple_of_immutables()
    print('ok TestCopy.test_deepcopy_tuple_of_immutables')


def _TestCopy__test_exceptions():
    t = TestCopy()
    t.test_exceptions()
    print('ok TestCopy.test_exceptions')


_TestCopy__test_copy_basic()
_TestCopy__test_copy_dict()
_TestCopy__test_copy_frozenset()
_TestCopy__test_copy_function()
_TestCopy__test_copy_list()
_TestCopy__test_copy_set()
_TestCopy__test_deepcopy_basic()
_TestCopy__test_deepcopy_empty_tuple()
_TestCopy__test_deepcopy_function()
_TestCopy__test_deepcopy_tuple()
_TestCopy__test_deepcopy_tuple_of_immutables()
_TestCopy__test_exceptions()
