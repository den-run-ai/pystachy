# pystachy: dynamic-any
from typing import Any


class Leaf:
    def __init__(self, action: int, result: bool):
        self.action = action
        self.result = result

    def __eq__(self, other: Any) -> bool:
        print('leaf', self.action, self.result)
        if self.action == 1:
            left[0].clear()
            right[0].clear()
        elif self.action == 2:
            left.clear()
        elif self.action == 3:
            left.clear()
            right.clear()
        elif self.action == 4:
            left.append([Leaf(0, True)])
            right.append(['later'])
        elif self.action == 5:
            raise ValueError('nested leaf')
        return self.result


left: list[list[Leaf]] = [[Leaf(0, True)]]
right: list[list[str]] = [['first']]
print('direct', left == right, right == left, left != right)
for action in [1, 2, 3, 4]:
    for result in [False, True]:
        left = [[Leaf(action, result)]]
        right = [['first']]
        left_alias = left
        right_alias = right
        print('mutation', action, result, left == right)
        print('aliases', left is left_alias, right is right_alias, len(left), len(right))
left = [[Leaf(5, True)]]
right = [['first']]
try:
    print(left == right)
except ValueError as error:
    print(error)
finally:
    print('cleanup')
left = [[Leaf(5, True)]]
right = []
print('different lengths', left == right)


class Holder:
    def __init__(self):
        self.items = [[Leaf(0, True)]]

    def __eq__(self, other: 'Holder') -> bool:
        print('comparison ran')
        return self.items == other.items


class Peer:
    def __init__(self):
        self.items = [['peer']]


holder: Any = Holder()
peer: Any = Peer()
print('boxed', holder == peer, peer == holder, holder != peer)
