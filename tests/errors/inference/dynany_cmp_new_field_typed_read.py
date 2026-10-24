# error: 'Peer' object has no attribute 'flag'
# pystachy: dynamic-any
from typing import Any


class Peer:
    pass


class Writer:
    def __eq__(self, other: Any) -> bool:
        other.flag = True
        return True


peer = Peer()
x: Any = Writer()
y: Any = peer
print(x == y)
print(peer.flag)
