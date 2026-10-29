# pystachy: dynamic-any
from typing import Any


class Leaf:
    def __init__(self, action: int, result: bool):
        self.action = action
        self.result = result

    def __eq__(self, other: Any) -> bool:
        print('leaf', self.action, self.result)
        if self.action == 1:
            left.clear()
        elif self.action == 2:
            right.clear()
        elif self.action == 3:
            left.clear()
            right.clear()
        elif self.action == 4:
            del left['later']
        elif self.action == 5:
            left['later'] = [Leaf(0, False)]
        elif self.action == 6:
            for i in range(6):
                key = str(i)
                left[key] = [Leaf(0, True)]
                right[key] = ['new']
        elif self.action == 7:
            raise ValueError('dict value')
        return self.result


left: dict[str, list[Leaf]] = {'first': [Leaf(0, True)]}
right: dict[str, list[str]] = {'first': ['first']}
print('direct', left == right, right == left, left != right)
for action in [1, 2, 3, 4, 5, 6]:
    for result in [False, True]:
        left = {'first': [Leaf(action, result)], 'later': [Leaf(0, True)]}
        right = {'first': ['first'], 'later': ['later']}
        left_alias = left
        right_alias = right
        print('mutation', action, result, left == right)
        print('aliases', left is left_alias, right is right_alias, len(left), len(right))
left = {'first': [Leaf(7, True)]}
right = {'first': ['first']}
try:
    print(left == right)
except ValueError as error:
    print(error)
finally:
    print('cleanup')
right = {'other': ['first']}
print('missing key', left == right)
right = {}
print('different lengths', left == right)
left = {}
print('empty', left == right)

ints = {1: [Leaf(0, True)]}

int_tuples = {(1, 'first'): [Leaf(0, True)]}
bool_tuples: dict[tuple[bool, str], list[str]] = {(True, 'first'): ['first']}
print('tuple keys', int_tuples == bool_tuples, bool_tuples == int_tuples)
string_keys = {'1': ['first']}
print('different key types', ints == string_keys)


class Holder:
    def __init__(self):
        self.items = {'key': [Leaf(0, True)]}

    def __eq__(self, other: 'Holder') -> bool:
        print('comparison ran')
        return self.items == other.items


class Peer:
    def __init__(self):
        self.items = {'key': ['peer']}


holder: Any = Holder()
peer: Any = Peer()
print('boxed', holder == peer, peer == holder, holder != peer)
