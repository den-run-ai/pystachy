# CPython 3.13.16 TestCmpToKey assertions from Lib/test/test_functools.py
# at commit cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256:
# ec00d729ddde2de6412237b3f8f4196bc0777ce9d0bf99fd69071fb44ce72fd5.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt.
# test_obj_field and test_sort_int retain all substantive assertions. Selections
# from test_cmp_to_key, test_cmp_to_key_arguments and test_bad_cmp
# are PARTIAL: mixed-type keys, invalid arguments as runtime failures, arbitrary
# comparator results and collections.abc.Hashable reflection are unsupported.
# test_hash maps to a compile rejection in errors/lib_functools_cmp_to_key_hash.py.
from functools import cmp_to_key


def compare(x: int, y: int) -> int:
    return (x > y) - (x < y)


key = cmp_to_key(compare)
assert key(3) == key(3)
assert key(3) > key(1)
assert key(3) >= key(3)
keyword_key = cmp_to_key(mycmp=compare)
assert keyword_key(obj=3) == keyword_key(obj=3)
assert keyword_key(obj=3) > keyword_key(obj=1)
assert keyword_key(50).obj == 50
try:
    key(3) > 1
except TypeError:
    pass
else:
    raise AssertionError('non-key comparison accepted')
try:
    1 < key(3)
except TypeError:
    pass
else:
    raise AssertionError('reflected non-key comparison accepted')


class Other:
    def __init__(self, obj: int) -> None:
        self.obj = obj


try:
    key(3) > Other(1)
except TypeError:
    pass
else:
    raise AssertionError('unrelated object with .obj accepted')


def descending(x: int, y: int) -> int:
    return y - x


assert sorted(range(5), key=cmp_to_key(descending)) == [4, 3, 2, 1, 0]
def broken(x: int, y: int) -> int:
    raise ZeroDivisionError


broken_key = cmp_to_key(broken)
try:
    broken_key(3) > broken_key(1)
except ZeroDivisionError:
    pass
else:
    raise AssertionError('comparator failure was swallowed')

# Additional subset cases exercise every comparison, obj writes, separate
# factories, homogeneous strings, stable and reverse sorting, min/max, closures.
assert key(1) < key(2)
assert key(1) <= key(2)
assert key(2) <= key(2)
assert key(2) >= key(2)
assert key(1) != key(2)
assert not (key(1) > key(2))
mutable_key = key(1)
mutable_key.obj = 4
assert mutable_key > key(3)
values = [3, 1, 2, 5, 4]
values.sort(key=cmp_to_key(descending))
assert values == [5, 4, 3, 2, 1]
assert sorted(values, key=key, reverse=True) == values
assert min(values, key=key) == 1
assert max(values, key=key) == 5


def compare_text(x: str, y: str) -> int:
    return (x.lower() > y.lower()) - (x.lower() < y.lower())


assert sorted(['b', 'A', 'B', 'a'], key=cmp_to_key(compare_text)) == ['A', 'a', 'b', 'B']
assert sorted(['b', 'A', 'B', 'a'], key=cmp_to_key(compare_text), reverse=True) == ['b', 'B', 'A', 'a']


def make_key(direction):
    def compare_direction(x: int, y: int) -> int:
        return direction * (x - y)

    return cmp_to_key(compare_direction)


assert sorted([3, 1, 2], key=make_key(-1)) == [3, 2, 1]
assert sorted([3, 1, 2], key=make_key(1)) == [1, 2, 3]
assert sorted([3, 1, 2], key=cmp_to_key(lambda x, y: x - y)) == [1, 2, 3]
assert sorted(['bbb', 'a', 'cc'], key=cmp_to_key(lambda x, y: len(x) - len(y))) == ['a', 'cc', 'bbb']
print('cmp_to_key: TestCmpToKey.test_obj_field and test_sort_int; partial methods and subset edge cases')
