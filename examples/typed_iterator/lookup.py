"""A three-operation stored interface with fixed key and value contracts."""
from typing import Callable, Generic, TypeVar


K = TypeVar("K")
V = TypeVar("V")


class TypedLookup(Generic[K, V]):
    def __init__(self, read: Callable[[K], V], contains: Callable[[K], bool],
                 size: Callable[[], int]) -> None:
        self._read: Callable[[K], V] = read
        self._contains: Callable[[K], bool] = contains
        self._size: Callable[[], int] = size

    def __getitem__(self, key: K) -> V:
        return self._read(key)

    def __contains__(self, key: K) -> bool:
        return self._contains(key)

    def __len__(self) -> int:
        return self._size()


def dict_lookup(values: dict[K, V]) -> TypedLookup[K, V]:
    """Retain a live dictionary behind read, membership and length operations."""
    def read(key: K) -> V:
        return values[key]

    def contains(key: K) -> bool:
        return key in values

    def size() -> int:
        return len(values)

    return TypedLookup(read, contains, size)


def index_lookup(values: list[V]) -> TypedLookup[int, V]:
    """Expose a live list as a lookup whose keys are its nonnegative indices."""
    def read(key: int) -> V:
        if key < 0 or key >= len(values):
            raise KeyError(key)
        return values[key]

    def contains(key: int) -> bool:
        return 0 <= key < len(values)

    def size() -> int:
        return len(values)

    return TypedLookup(read, contains, size)
