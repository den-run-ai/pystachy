# pystachy: dynamic-any
from typing import Any


class Leaf:
    def __init__(self, result: bool):
        self.result = result

    def __eq__(self, other: Any) -> bool:
        print('leaf', self.result)
        return self.result


fixed = ([Leaf(True)], {'key': [Leaf(True)]})
peer = (['peer'], {'key': ['peer']})
print('fixed', fixed == peer, peer == fixed, fixed != peer)
print('different lengths', fixed == (['peer'],))
other: tuple[str, ...] = ('first', 'later')
print('fixed variable', (Leaf(True), Leaf(True)) == other, other == (Leaf(True), Leaf(True)))
other = ('first',)
print('variable lengths', (Leaf(True), Leaf(True)) == other, other == (Leaf(True), Leaf(True)))
other = ('first', 'later', 'last')
print('variable longer', (Leaf(True), Leaf(True)) == other)
false_fixed = ([Leaf(False)], [Leaf(True)])
print('short circuit', false_fixed == (['first'], ['later']))
nullable: list[list[Leaf] | None] = [None, [Leaf(True)]]
nullable_peer: list[list[str] | None] = [None, ['first']]
print('nullable', nullable == nullable_peer, nullable_peer == nullable)
nullable_peer[0] = ['other']
print('different None', nullable == nullable_peer)


class Holder:
    def __init__(self):
        self.items = ([Leaf(True)],)

    def __eq__(self, other: 'Holder') -> bool:
        print('comparison ran')
        return self.items == other.items


class Peer:
    def __init__(self):
        self.items = (['peer'],)


holder: Any = Holder()
peer_holder: Any = Peer()
print('boxed', holder == peer_holder, peer_holder == holder, holder != peer_holder)
