# Objects as dict keys and set elements: the effects of their lookups (object_keys.fx) and the
# lookups dictfuse fuses (object_keys.calls). A key hashed by identity runs no code of the program,
# but the __repr__ of a KeyError naming it (Shown: U where the op may raise, getitem, not in);
# one hashed by its class runs __hash__ and __eq__ at each lookup (Hashed: U), which CPython runs
# again at the lookup after `in`, so that those two lookups stay apart (dictfuse fuses them only
# for the others). A copy of a dict of the latter may run __eq__ (U), and del d[k] of one hashes
# k where d.pop(k) would not (pys_dict_del); a copy of the others runs no code.


class Node:
    pass


class Shown:
    def __repr__(self) -> str:
        return "Shown()"


class Hashed:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: "Hashed") -> bool:
        return self.v == other.v

    def __hash__(self) -> int:
        return self.v


def node_get(d: dict[Node, int], n: Node) -> int:
    return d[n]


def node_in(s: set[Node], n: Node) -> bool:
    return n in s


def node_fused(d: dict[Node, int], n: Node) -> int:
    if n in d:
        return d[n]
    return 0


def shown_get(d: dict[Shown, int], n: Shown) -> int:
    return d[n]


def shown_in(d: dict[Shown, int], n: Shown) -> bool:
    return n in d


def hashed_in(d: dict[Hashed, int], n: Hashed) -> bool:
    return n in d


def hashed_fused(d: dict[Hashed, int], n: Hashed) -> int:
    if n in d:
        return d[n]
    return 0


def node_hash(n: Node) -> int:
    return hash(n)


def node_copy(d: dict[Node, int]) -> int:
    return len(dict(d)) + len(d.copy())


def hashed_copy(d: dict[Hashed, int]) -> int:
    return len(dict(d)) + len(d.copy())


def node_del(d: dict[Node, int], n: Node) -> None:
    del d[n]


def hashed_del(d: dict[Hashed, int], n: Hashed) -> None:
    del d[n]


node_get({Node(): 1}, Node())
node_in({Node()}, Node())
node_fused({Node(): 1}, Node())
shown_get({Shown(): 1}, Shown())
shown_in({Shown(): 1}, Shown())
hashed_in({Hashed(1): 1}, Hashed(1))
hashed_fused({Hashed(1): 1}, Hashed(1))
node_hash(Node())
node_copy({Node(): 1})
hashed_copy({Hashed(1): 1})
node_del({Node(): 1}, Node())
hashed_del({Hashed(1): 1}, Hashed(1))
