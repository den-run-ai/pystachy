# A list subclass with __slots__ and __hash__, as functools._HashedSeq is: the hash is computed
# once and kept in a slot, and equality stays list's, so the object is a dict key that an equal
# one finds.


class _HashedSeq(list):
    __slots__ = "hashvalue"

    def __init__(self, tup: tuple[int, int, int]) -> None:
        self[:] = tup
        self.hashvalue: int = hash(tup)

    def __hash__(self) -> int:
        return self.hashvalue


def _make_key(a: int, b: int, c: int) -> _HashedSeq:
    return _HashedSeq((a, b, c))


cache: dict[_HashedSeq, str] = {}
hits = 0
for a, b, c in [(1, 2, 3), (4, 5, 6), (1, 2, 3), (3, 2, 1), (4, 5, 6), (1, 2, 3)]:
    key = _make_key(a, b, c)
    if key in cache:
        hits += 1
    else:
        cache[key] = "{}-{}-{}".format(a, b, c)
print(hits, len(cache), sorted(cache.values()))
k = _make_key(1, 2, 3)
print(k, len(k), k[0], k.hashvalue == hash((1, 2, 3)), hash(k) == hash((1, 2, 3)))
print(k == _make_key(1, 2, 3), k == _make_key(3, 2, 1), k == [1, 2, 3], k != [1, 2, 3], cache[k])
seen = {_make_key(1, 1, 1), _make_key(1, 1, 1), _make_key(2, 2, 2)}
print(len(seen), _make_key(2, 2, 2) in seen, _make_key(9, 9, 9) in seen)
print(hasattr(k, "__dict__"), hasattr(k, "hashvalue"))
