"""Pystachy's collections: deque, a generic class written for the subset (lib/README.md).

CPython's collections is Lib/collections/__init__.py over the C type _collections.deque
(Modules/_collectionsmodule.c); this deque follows that C code's behaviour and messages. Its items
have one type, T, which the iterable it is made from gives (deque([1, 2])), or the annotation of
where it goes (q: deque[int] = deque()), or the call (deque[int]()).
"""

from typing import Generic, Iterable, Iterator, Self, TypeVar

__all__ = ["deque"]

_T = TypeVar("_T")


class deque(Generic[_T]):
    """A list-like sequence optimized for data accesses near its endpoints."""

    def __init__(self, iterable: Iterable[_T] = (), maxlen: int | None = None) -> None:
        if maxlen is not None and maxlen < 0:
            raise ValueError("maxlen must be non-negative")
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

    def appendleft(self, x: _T) -> None:
        """Add an element to the left side of the deque."""
        if self.maxlen == 0:
            return
        if self._full():
            self.pop()
        self._left.append(x)

    def pop(self) -> _T:
        """Remove and return the rightmost element."""
        if not self._right:
            if not self._left:
                raise IndexError("pop from an empty deque")
            # the right half of the left items, in order
            k = (len(self._left) + 1) // 2
            self._right = list(reversed(self._left[:k]))
            self._left = self._left[k:]
        return self._right.pop()

    def popleft(self) -> _T:
        """Remove and return the leftmost element."""
        if not self._left:
            if not self._right:
                raise IndexError("pop from an empty deque")
            k = (len(self._right) + 1) // 2
            self._left = list(reversed(self._right[:k]))
            self._right = self._right[k:]
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
        return self._items().count(x)

    def _find(self, items: list[_T], x: _T, start: int, stop: int) -> int:
        # the index of the first of items[start:stop] equal to x, or -1, compared from the left as
        # CPython's deque compares (item == x, where an item that is x is equal to it without a call
        # of __eq__): `x in one`, of a list whose item is each item in turn, compares so
        one = [x]
        for i in range(start, stop):
            one[0] = items[i]
            if x in one:
                return i
        return -1

    def index(self, x: _T, start: int = 0, stop: int = 9223372036854775807) -> int:
        """Return first index of value.

        Raises ValueError if the value is not present.
        """
        items = self._items()
        n = len(items)
        if start < 0:
            start = max(start + n, 0)
        if stop < 0:
            stop = max(stop + n, 0)
        i = self._find(items, x, start, min(stop, n))
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
        if i <= len(self._left):
            self._left.insert(len(self._left) - i, x)
        else:
            self._right.insert(i - len(self._left), x)

    def remove(self, x: _T) -> None:
        """Remove first occurrence of value."""
        items = self._items()
        i = self._find(items, x, 0, len(items))
        if i < 0:
            raise ValueError(f"{x!r} is not in deque")
        del items[i]
        self._set(items)

    def reverse(self) -> None:
        """Reverse *IN PLACE*."""
        self._left, self._right = self._right, self._left

    def rotate(self, n: int = 1) -> None:
        """Rotate the deque n steps to the right (default n=1).  If n is negative, rotates left."""
        size = len(self._left) + len(self._right)
        if size <= 1:
            return
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
        if i < len(self._left):
            del self._left[len(self._left) - 1 - i]
        else:
            del self._right[i - len(self._left)]

    def __len__(self) -> int:
        return len(self._left) + len(self._right)

    def __bool__(self) -> bool:
        return len(self._left) + len(self._right) > 0

    def __contains__(self, x: _T) -> bool:
        return x in self._items()  # (from the left, as count())

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
        if n <= 0 or not items:
            self.clear()
            return self
        if self.maxlen is not None and len(items) * n > self.maxlen:
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
