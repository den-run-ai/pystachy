"""Optional dense masks for integer IDs in a fixed [0, capacity) universe.

Use with CPython or Pystachy. This is an example library, not a replacement for
Python's set: storage and Boolean operations scale with capacity, not cardinality.
"""


class IdSet:
    """Mutable bounded IDs; operations return independent masks with the same capacity.

    Each word uses 63 bits, keeping every stored value within signed int64. Do not
    mutate the private storage or capacity: checked access preserves zero padding.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("capacity must be nonnegative")
        self._capacity = capacity
        n = capacity // 63
        if capacity % 63:
            n += 1
        self._words: list[int] = [0] * n

    def capacity(self) -> int:
        return self._capacity

    def storage_words(self) -> int:
        """Number of int64 payload words under Pystachy; excludes allocation headers."""
        return len(self._words)

    def _check_id(self, value: int) -> None:
        if value < 0 or value >= self._capacity:
            raise ValueError("ID outside [0, capacity)")

    def _check_other(self, other: "IdSet") -> None:
        if self._capacity != other._capacity:
            raise ValueError("ID universes differ")

    def add(self, value: int) -> None:
        self._check_id(value)
        index = value // 63
        self._words[index] |= 1 << (value % 63)

    def discard(self, value: int) -> None:
        self._check_id(value)
        index = value // 63
        self._words[index] &= ~(1 << (value % 63))

    def contains(self, value: int) -> bool:
        self._check_id(value)
        return (self._words[value // 63] & (1 << (value % 63))) != 0

    def count(self) -> int:
        total = 0
        for word in self._words:
            total += word.bit_count()
        return total

    def ids(self) -> list[int]:
        """Return each ID once, in ascending order."""
        result: list[int] = []
        for index in range(len(self._words)):
            word = self._words[index]
            while word:
                low = word & -word
                result.append(index * 63 + low.bit_length() - 1)
                word &= word - 1
        return result

    def intersection_count(self, other: "IdSet") -> int:
        """Count common IDs without allocating an intermediate mask or ID list."""
        self._check_other(other)
        total = 0
        for index in range(len(self._words)):
            total += (self._words[index] & other._words[index]).bit_count()
        return total

    def intersection(self, other: "IdSet") -> "IdSet":
        self._check_other(other)
        result = IdSet(self._capacity)
        for index in range(len(self._words)):
            result._words[index] = self._words[index] & other._words[index]
        return result

    def union(self, other: "IdSet") -> "IdSet":
        self._check_other(other)
        result = IdSet(self._capacity)
        for index in range(len(self._words)):
            result._words[index] = self._words[index] | other._words[index]
        return result

    def difference(self, other: "IdSet") -> "IdSet":
        self._check_other(other)
        result = IdSet(self._capacity)
        for index in range(len(self._words)):
            result._words[index] = self._words[index] & ~other._words[index]
        return result


def from_ids(capacity: int, values: list[int]) -> IdSet:
    result = IdSet(capacity)
    for value in values:
        result.add(value)
    return result
