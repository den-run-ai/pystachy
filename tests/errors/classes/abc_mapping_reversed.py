# error: reversed() of Pairs by its __len__ and __getitem__ is not supported
# A Mapping is not reversible: CPython's sets __reversed__ = None, which raises TypeError where
# reversed() of one runs; Pystachy rejects the call
from collections.abc import Mapping


class Pairs(Mapping):
    def __getitem__(self, k: int) -> int:
        return k * 2

    def __iter__(self):
        return iter([1, 2])

    def __len__(self) -> int:
        return 2


print(list(reversed(Pairs())))
