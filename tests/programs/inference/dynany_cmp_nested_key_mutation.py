# pystachy: dynamic-any
from typing import Any

record = False
action = 0


class Key:
    def __init__(self, number: int):
        self.number = number

    def __hash__(self) -> int:
        if record:
            print('hash left', self.number)
        return 1

    def __eq__(self, other: Any) -> bool:
        if record:
            print('left key', self.number, other.number)
        return self.number == other.number


class PeerKey:
    def __init__(self, number: int):
        self.number = number

    def __hash__(self) -> int:
        if record:
            print('hash right', self.number)
        return 1

    def __eq__(self, other: Any) -> bool:
        global action
        if record:
            print('right key', self.number, other.number)
        current = action
        action = 0
        if current == 1:
            right.clear()
        elif current == 2:
            left.clear()
        elif current == 3:
            right[first] = ['changed']
        elif current == 4:
            left[source] = [Leaf(False)]
        elif current == 5 or current == 9:
            del right[first]
            right[PeerKey(0)] = ['reinserted']
        elif current == 6:
            for i in range(3, 9):
                right[PeerKey(i)] = ['grown']
        elif current == 7:
            for i in range(3, 9):
                left[Key(i)] = [Leaf(True)]
                right[PeerKey(i)] = ['grown']
        elif current == 8:
            raise ValueError('key first')
        if current == 9:
            return False
        return self.number == other.number


class Leaf:
    def __init__(self, result: bool):
        self.result = result

    def __eq__(self, other: Any) -> bool:
        print('value', self.result, other)
        return self.result


left: dict[Key, list[Leaf]] = {}
right: dict[PeerKey, list[str]] = {}
source = Key(0)
first = PeerKey(0)
for case in range(10):
    record = False
    source = Key(0)
    first = PeerKey(0)
    left = {source: [Leaf(True)], Key(1): [Leaf(True)], Key(2): [Leaf(True)]}
    right = {first: ['zero'], PeerKey(1): ['one'], PeerKey(2): ['two']}
    alias_left = left
    alias_right = right
    record = True
    action = case
    print('case', case)
    try:
        print('equal', left == right)
    except ValueError as error:
        print(error)
    finally:
        print('aliases', left is alias_left, right is alias_right, len(left), len(right))

# Mutating a same-layout key must use the same restart discipline too.
record = False
source = Key(0)
first = PeerKey(0)
left = {source: [Leaf(True)]}
right = {first: ['zero']}
same_keys = {PeerKey(0): [Leaf(True)]}
record = True
action = 1
print('same layout clear', same_keys == right)


# A native integer-zero target key has raw slot 0, also the deleted slot's
# value. The lookup must check the live index after its reflected callback.
zero_action = 0
zero: dict[int, list[str]] = {}


class ZeroKey:
    def __hash__(self) -> int:
        print('zero hash')
        return 0

    def __eq__(self, other: Any) -> bool:
        global zero_action
        print('zero key', other)
        current = zero_action
        zero_action = 0
        if current == 1:
            del zero[0]
        elif current == 2:
            zero.popitem()
            zero[0] = ['new zero']
        elif current == 3:
            zero.clear()
        return True


for case in range(4):
    zero = {0: ['zero']}
    left_zero = {ZeroKey(): [Leaf(True)]}
    zero_action = case
    print('zero case', case, left_zero == zero, len(zero))
