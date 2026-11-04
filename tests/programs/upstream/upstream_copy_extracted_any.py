# pystachy: dynamic-any
# CPython 3.13.16 Lib/test/test_copy.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 e137a3f2b5d5bbfe42eba2e1923d84de15a2e5ce8e6e330b88c88672982db016).
# Mechanically extracted with tools/cpython_test_methods.py (tests/upstream/core-sweep.md).
"""Unit tests for the copy module."""
import copy
import weakref

class TestCopy:

    def test_deepcopy_list(self):
        x = [[1, 2], 3]
        y = copy.deepcopy(x)
        assert y == x
        assert x is not y
        assert x[0] is not y[0]

    def test_deepcopy_dict(self):
        x = {'foo': [1, 2], 'bar': 3}
        y = copy.deepcopy(x)
        assert y == x
        assert x is not y
        assert x['foo'] is not y['foo']

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


def _TestCopy__test_deepcopy_list():
    t = TestCopy()
    t.test_deepcopy_list()
    print('ok TestCopy.test_deepcopy_list')


def _TestCopy__test_deepcopy_dict():
    t = TestCopy()
    t.test_deepcopy_dict()
    print('ok TestCopy.test_deepcopy_dict')


_TestCopy__test_deepcopy_list()
_TestCopy__test_deepcopy_dict()
