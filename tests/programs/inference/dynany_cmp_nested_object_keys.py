# pystachy: dynamic-any
from typing import Any


class Key:
    def __init__(self, name: str, code: int):
        self.name = name
        self.code = code

    def __hash__(self) -> int:
        print('hash', self.name)
        if self.code < 0:
            raise RuntimeError('rehash')
        return self.code

    def __eq__(self, other: Any) -> bool:
        print('key', self.name)
        return True


class PeerKey:
    def __init__(self, code: int):
        self.code = code

    def __hash__(self) -> int:
        print('peer hash', self.code)
        return self.code

class Leaf:
    def __eq__(self, other: Any) -> bool:
        print('leaf')
        return True


class Holder:
    def __init__(self):
        self.items = {Key('left', 0): [Leaf()]}

    def __eq__(self, other: 'Holder') -> bool:
        print('comparison ran')
        return self.items == other.items


class SameKeys:
    def __init__(self):
        self.items = {Key('right', 0): ['peer']}


class DifferentKeys:
    def __init__(self):
        self.items = {PeerKey(0): ['peer']}


class IntKeys:
    def __init__(self):
        self.items = {0: ['peer']}


a: Any = Holder()
peers: list[Any] = [SameKeys(), DifferentKeys(), IntKeys()]
for peer in peers:
    b: Any = peer
    print('boxed', a == b, b == a, a != b)

# Construction is the last time __hash__ may run. Identity must find the
# shared key even though later __hash__ calls would return a different value.
key = Key('shared', 1)
left = {key: [Leaf()]}
right = {key: ['peer']}
key.code = -99
print('same key', left == right, right == left)

left_tuple = {(Key('tuple', 1), 2): [Leaf()]}
right_tuple = {(1, 2): ['peer']}
print('tuple keys', left_tuple == right_tuple, right_tuple == left_tuple)

left_string = {Key('string', hash('key')): [Leaf()]}
right_string = {'key': ['peer']}
print('string keys', left_string == right_string, right_string == left_string)

wrong_hash = {PeerKey(2): ['peer']}
print('hash mismatch', left == wrong_hash)
empty: dict[int, list[str]] = {}
print('empty', left == empty)


class SharedKey:
    def __init__(self):
        self.code = 0

    def __hash__(self) -> int:
        print('shared hash', self.code)
        return self.code

    def __eq__(self, other: Any) -> bool:
        print('shared equality must not run')
        return False


# Source and target keys share identity across native and boxed layouts. The
# hash changed between insertions, but both probes visit the shared key first.
shared = SharedKey()
native: dict[SharedKey, int] = {shared: 1}
shared.code = 8
boxed: dict[Any, Any] = {shared: 1}
print('shared boxed key', native == boxed, boxed == native)
