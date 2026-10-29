# pystachy: dynamic-any
from typing import Any
from mods.dynany_dict_sources import sources


class Key:
    def __hash__(self) -> int:
        print('hash')
        return 0

    def __eq__(self, other: Any) -> bool:
        print('key', other)
        return True


class Leaf:
    def __eq__(self, other: Any) -> bool:
        print('leaf', other)
        return True


left = {Key(): [Leaf()]}
for right in sources():
    alias = right
    print('compare', left == right, right == left, right is alias)
    print('keys', list(right), sorted(set(right)), list(reversed(right)))
    copy = right.copy()
    print('pop', copy.popitem(), len(copy))

# Scalar zero is a live key with Python hash 0. Deletions, compaction,
# copies, iteration and set transfers must distinguish it from a hole.
numbers = {i: i for i in range(15)}
for i in range(1, 15):
    numbers.pop(i)
print('zero', numbers, dict(numbers), numbers.copy(), dict.fromkeys(numbers, 0))
print('set', sorted(set(numbers)), sorted({0, 1} - set(numbers)))
print('pop zero', numbers.popitem(), numbers)
numbers[0] = 0
print('reinsert zero', numbers)
