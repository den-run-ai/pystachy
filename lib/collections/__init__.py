"""Pystachy's collections: deque, a generic class written for the subset (lib/README.md).

CPython's collections is Lib/collections/__init__.py over the C type _collections.deque
(Modules/_collectionsmodule.c); this deque follows that C code's behaviour and messages. Its items
have one type, T, which an explicitly typed list argument gives. Empty compiled deques need a
list with an item annotation; runtime Generic aliases such as deque[int]() remain unsupported.
"""

from typing import Generic, Iterator, Self, TypeVar

__all__ = ["deque"]

_T = TypeVar("_T")


class deque(Generic[_T]):
    """A list-like sequence optimized for data accesses near its endpoints."""

    # Pystachy port: bind T from a list argument; Generic[T] annotations/calls are not supported.
    def __init__(self, iterable: list[_T] = (), maxlen: int | None = None) -> None:
        if maxlen is not None and maxlen < 0:
            raise ValueError("maxlen must be non-negative")
        self._state = 0  # endpoint mutations invalidate CPython's active comparisons
        self.maxlen = maxlen  # (maximum size of a deque or None if unbounded)
        # the items, in two lists: the left ones reversed (the leftmost item is _left[-1]) and the
        # right ones in order (the rightmost is _right[-1]), so that each end pops and appends in
        # amortized O(1): an end that runs out takes half of the other list's items
        self._left: list[_T] = []
        self._right: list[_T] = []
        for x in iterable:
            self.append(x)

    def _items(self) -> list[_T]:
        # the items, from left to right
        return list(reversed(self._left)) + self._right

    def _set(self, items: list[_T]) -> None:
        self._left = []
        self._right = items

    def _full(self) -> bool:
        return self.maxlen is not None and len(self._left) + len(self._right) >= self.maxlen

    def append(self, x: _T) -> None:
        """Add an element to the right side of the deque."""
        if self.maxlen == 0:
            return
        if self._full():
            self.popleft()
        self._right.append(x)
        self._state += 1

    def appendleft(self, x: _T) -> None:
        """Add an element to the left side of the deque."""
        if self.maxlen == 0:
            return
        if self._full():
            self.pop()
        self._left.append(x)
        self._state += 1

    def pop(self) -> _T:
        """Remove and return the rightmost element."""
        if not self._right:
            if not self._left:
                raise IndexError("pop from an empty deque")
            # the right half of the left items, in order
            k = (len(self._left) + 1) // 2
            self._right = list(reversed(self._left[:k]))
            self._left = self._left[k:]
        self._state += 1
        return self._right.pop()

    def popleft(self) -> _T:
        """Remove and return the leftmost element."""
        if not self._left:
            if not self._right:
                raise IndexError("pop from an empty deque")
            k = (len(self._right) + 1) // 2
            self._left = list(reversed(self._right[:k]))
            self._right = self._right[k:]
        self._state += 1
        return self._left.pop()

    def extend(self, iterable) -> None:
        """Extend the right side of the deque with elements from the iterable."""
        items = list(iterable)  # (also of the deque itself: d.extend(d))
        for x in items:
            self.append(x)

    def extendleft(self, iterable) -> None:
        """Extend the left side of the deque with elements from the iterable."""
        items = list(iterable)
        for x in items:
            self.appendleft(x)

    def clear(self) -> None:
        """Remove all elements from the deque."""
        if self:
            self._state += 1
        self._left = []
        self._right = []

    def copy(self) -> Self:
        """Return a shallow copy of a deque."""
        d = deque(self._items(), self.maxlen)
        return d

    def __copy__(self) -> Self:
        """Return a shallow copy of a deque."""
        return self.copy()

    def count(self, x: _T) -> int:
        """Return number of occurrences of value."""
        state = self._state
        count = 0
        one = [x]
        for i in range(len(self)):
            one[0] = self[i]
            if x in one:  # item == x, with CPython's identity shortcut
                count += 1
            if state != self._state:
                raise RuntimeError("deque mutated during iteration")
        return count

    def _find(self, x: _T, start: int, stop: int, removing: bool = False) -> int:
        # Read live items: callbacks may replace/reverse them without changing CPython's state.
        # index/in return a successful match before checking state; remove checks state first.
        state = self._state
        one = [x]
        for i in range(start, stop):
            one[0] = self[i]
            same = x in one
            if same and not removing:
                return i
            if state != self._state:
                if removing:
                    raise IndexError("deque mutated during iteration")
                raise RuntimeError("deque mutated during iteration")
            if same:
                return i
        return -1

    def index(self, x: _T, start: int = 0, stop: int = 9223372036854775807) -> int:
        """Return first index of value.

        Raises ValueError if the value is not present.
        """
        n = len(self)
        if start < 0:
            start = max(start + n, 0)
        if stop < 0:
            stop = max(stop + n, 0)
        i = self._find(x, start, min(stop, n))
        if i < 0:
            raise ValueError(f"{x!r} is not in deque")
        return i

    def insert(self, i: int, x: _T) -> None:
        """Insert value before index."""
        if self._full():
            raise IndexError("deque already at its maximum size")
        n = len(self._left) + len(self._right)
        if i < 0:
            i = max(i + n, 0)
        i = min(i, n)
        self._state += 1
        if i <= len(self._left):
            self._left.insert(len(self._left) - i, x)
        else:
            self._right.insert(i - len(self._left), x)

    def remove(self, x: _T) -> None:
        """Remove first occurrence of value."""
        i = self._find(x, 0, len(self), True)
        if i < 0:
            raise ValueError(f"{x!r} is not in deque")
        del self[i]  # preserve same-size replacements made by comparison callbacks

    def reverse(self) -> None:
        """Reverse *IN PLACE*."""
        self._left, self._right = self._right, self._left

    def rotate(self, n: int = 1) -> None:
        """Rotate the deque n steps to the right (default n=1).  If n is negative, rotates left."""
        size = len(self._left) + len(self._right)
        if size <= 1:
            return
        self._state += 1  # CPython also invalidates comparisons for rotate(0).
        n %= size
        if n == 0:
            return
        items = self._items()
        self._set(items[size - n:] + items[:size - n])

    def _at(self, i: int) -> int:
        # the position of index i (also negative) from the left, or IndexError
        n = len(self._left) + len(self._right)
        if i < 0:
            i += n
        if i < 0 or i >= n:
            raise IndexError("deque index out of range")
        return i

    def __getitem__(self, i: int) -> _T:
        i = self._at(i)
        if i < len(self._left):
            return self._left[len(self._left) - 1 - i]
        return self._right[i - len(self._left)]

    def __setitem__(self, i: int, x: _T) -> None:
        i = self._at(i)
        if i < len(self._left):
            self._left[len(self._left) - 1 - i] = x
        else:
            self._right[i - len(self._left)] = x

    def __delitem__(self, i: int) -> None:
        i = self._at(i)
        self._state += 1
        if i < len(self._left):
            del self._left[len(self._left) - 1 - i]
        else:
            del self._right[i - len(self._left)]

    def __len__(self) -> int:
        return len(self._left) + len(self._right)

    def __bool__(self) -> bool:
        return len(self._left) + len(self._right) > 0

    def __contains__(self, x: _T) -> bool:
        return self._find(x, 0, len(self)) >= 0

    def __iter__(self) -> Iterator[_T]:
        # the items when the loop starts (an iterator class, which CPython's deque has, is not
        # supported: a loop does not see the deque change)
        return iter(self._items())

    def __eq__(self, other: Self) -> bool:
        return self._items() == other._items()

    def __ne__(self, other: Self) -> bool:
        return self._items() != other._items()

    def __lt__(self, other: Self) -> bool:
        return self._items() < other._items()

    def __le__(self, other: Self) -> bool:
        return self._items() <= other._items()

    def __gt__(self, other: Self) -> bool:
        return self._items() > other._items()

    def __ge__(self, other: Self) -> bool:
        return self._items() >= other._items()

    def __add__(self, other: Self) -> Self:
        d = self.copy()
        d.extend(other._items())
        return d

    def __iadd__(self, iterable) -> Self:
        self.extend(iterable)
        return self

    def __mul__(self, n: int) -> Self:
        d = self.copy()
        d *= n
        return d

    def __imul__(self, n: int) -> Self:
        items = self._items()
        if n == 1 or not items:
            return self
        if n <= 0:
            self.clear()
            return self
        if n > 9223372036854775807 // len(items):
            raise MemoryError  # CPython rejects a repeated length larger than PY_SSIZE_T_MAX.
        if self.maxlen is not None and n > self.maxlen // len(items):
            # The comparison divides first to avoid signed-64-bit overflow for large n.
            # (the leftmost items are trimmed, as appends past maxlen trim them)
            n = min(n, self.maxlen // len(items) + 2)
        self.clear()
        for _ in range(n):
            for x in items:
                self.append(x)
        return self

    def __repr__(self) -> str:
        if self.maxlen is None:
            return f"deque({self._items()!r})"
        return f"deque({self._items()!r}, maxlen={self.maxlen})"
