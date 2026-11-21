# The ABCs' abstract methods: making an object of a class that leaves one raises CPython's
# TypeError, which names them in order; a Mapping (whose __eq__ makes it unhashable) and a Set
from collections.abc import Mapping, MutableSequence, Set


class Missing(Mapping):
    def __getitem__(self, k: str) -> int:
        return 0


class Half(MutableSequence):
    def __getitem__(self, i: int) -> int:
        return 0

    def __len__(self) -> int:
        return 0


class Empty(Set):
    def __contains__(self, x: int) -> bool:
        return False


try:
    Missing()
except TypeError as e:
    print("TypeError", e)
try:
    Half()
except TypeError as e:
    print("TypeError", e)
try:
    Empty()
except TypeError as e:
    print("TypeError", e)
