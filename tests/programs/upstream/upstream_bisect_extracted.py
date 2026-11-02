# CPython 3.13.16 Lib/test/test_bisect.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 c2cc55581e637768faa0f51cbb66acbaa6664eb023e287b37db687faefa2c1c4),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: TestInsortPython.test_backcompatibility, TestDocExamplePython.test_colors,
#   TestDocExamplePython.test_grades.
import bisect as py_bisect

class TestInsort:

    def test_backcompatibility(self):
        assert py_bisect.insort == py_bisect.insort_right

class TestInsortPython(TestInsort):
    pass

class TestDocExample:

    def test_grades(self):

        def grade(score):
            i = py_bisect.bisect([60, 70, 80, 90], score)
            return 'FDCBA'[i]
        result = [grade(score) for score in [33, 99, 77, 70, 89, 90, 100]]
        assert result == ['F', 'A', 'C', 'C', 'B', 'A', 'A']

    def test_colors(self):
        data = [('red', 5), ('blue', 1), ('yellow', 8), ('black', 0)]
        data.sort(key=lambda r: r[1])
        keys = [r[1] for r in data]
        bisect_left = py_bisect.bisect_left
        assert data[bisect_left(keys, 0)] == ('black', 0)
        assert data[bisect_left(keys, 1)] == ('blue', 1)
        assert data[bisect_left(keys, 5)] == ('red', 5)
        assert data[bisect_left(keys, 8)] == ('yellow', 8)

class TestDocExamplePython(TestDocExample):
    pass


def _TestInsortPython__test_backcompatibility():
    t = TestInsortPython()
    t.test_backcompatibility()
    print('ok TestInsortPython.test_backcompatibility')


def _TestDocExamplePython__test_colors():
    t = TestDocExamplePython()
    t.test_colors()
    print('ok TestDocExamplePython.test_colors')


def _TestDocExamplePython__test_grades():
    t = TestDocExamplePython()
    t.test_grades()
    print('ok TestDocExamplePython.test_grades')


_TestInsortPython__test_backcompatibility()
_TestDocExamplePython__test_colors()
_TestDocExamplePython__test_grades()
