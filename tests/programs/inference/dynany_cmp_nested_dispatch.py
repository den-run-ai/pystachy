# pystachy: dynamic-any
from typing import Any


class Leaf:
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other: Any) -> bool:
        print('leaf', self.name)
        return True


class Holder:
    def __init__(self):
        self.rows = [[Leaf('list')]]
        self.lookup = {(1, 'key'): [Leaf('dict')]}
        self.pair = ([Leaf('tuple')],)

    def __eq__(self, other: 'Holder') -> bool:
        print('comparison ran')
        return self.rows == other.rows and self.lookup == other.lookup and self.pair == other.pair


class Peer:
    def __init__(self):
        self.rows = [['list']]
        self.lookup: dict[tuple[bool, str], list[str]] = {(True, 'key'): ['dict']}
        self.pair = (['tuple'],)


holder: Any = Holder()
peer: Any = Peer()
print(holder == peer, peer == holder, holder != peer)
