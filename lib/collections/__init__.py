"""Pystachy's collections: deque, defaultdict, OrderedDict and Counter, generic classes written
for the subset (lib/README.md), and namedtuple(), which the compiler carries out.

CPython's collections is Lib/collections/__init__.py over the C types _collections.deque and
_collections.defaultdict (Modules/_collectionsmodule.c) and OrderedDict (Objects/odictobject.c,
which replaces the Python OrderedDict of Lib/collections/__init__.py). This deque and defaultdict
follow that C code's behaviour and messages; OrderedDict and Counter follow the Python classes,
with the C OrderedDict's messages. Their items have one type each, T (or K and V), bound by the
constructor's arguments, an annotation such as deque[int] or Counter[str], or an explicit
constructor such as deque[int](). CPython's mappings derive from dict; these hold dicts
instead, so isinstance(x, dict) is false for them, and keys(), values() and items() return
lists, as a dict's do here.

namedtuple() makes its class at compile time: the compiler compiles NAME = namedtuple(...) in a
module's top-level code, given literal arguments, as a class statement, a NamedTuple whose fields
the calls that make its objects type (a class template), and rejects every other use of the
function below, whose body never runs.
"""

from typing import Callable, Generic, Iterable, Iterator, Self, TypeVar

__all__ = ["deque", "defaultdict", "namedtuple", "OrderedDict", "Counter"]

# CPython's binds abc = _collections_abc, the module collections.abc; Pystachy's is builtin
import collections.abc as abc

_T = TypeVar("_T")
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


def namedtuple(typename, field_names, *, rename=False, defaults=None, module=None):
    """Returns a new subclass of tuple with named fields (made by the compiler: see above)."""
    raise NotImplementedError("namedtuple() is carried out by the compiler")


class deque(Generic[_T]):
    """A list-like sequence optimized for data accesses near its endpoints."""

    def __init__(self, iterable: Iterable[_T] = (), maxlen: int | None = None) -> None:
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

    def __iter__(self):
        return _deque_iterator(self)

    def __reversed__(self) -> Iterator[_T]:
        """Return a reverse iterator over the deque."""
        return iter(list(reversed(self._right)) + self._left)

    def _others(self, other: Self, op: str) -> list[_T]:
        # the items of the other operand of a comparison; None (an optional deque's) makes
        # CPython's TypeError, as deque_richcompare returns NotImplemented
        if other is None:
            raise TypeError(f"'{op}' not supported between instances of 'collections.deque' and 'NoneType'")
        return other._items()

    def __eq__(self, other: Self) -> bool:
        # (None is not equal: NotImplemented, then an identity test)
        return other is not None and self._items() == other._items()

    def __ne__(self, other: Self) -> bool:
        return other is None or self._items() != other._items()

    def __lt__(self, other: Self) -> bool:
        return self._items() < self._others(other, "<")

    def __le__(self, other: Self) -> bool:
        return self._items() <= self._others(other, "<=")

    def __gt__(self, other: Self) -> bool:
        return self._items() > self._others(other, ">")

    def __ge__(self, other: Self) -> bool:
        return self._items() >= self._others(other, ">=")

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


################################################################################
### Mappings
################################################################################

def _update(self, other) -> None:
    # MutableMapping.update's positional argument (odictobject.c's mutablemapping_update_arg; a
    # defaultdict's, dict_merge's): a dict's items, the pairs of a list, tuple or set, or else a
    # mapping object's keys and values. (Pystachy port: another iterable object of pairs, which
    # this takes for a mapping, is not supported: list(...) it first)
    if isinstance(other, dict):
        for key, value in other.items():
            self[key] = value
    elif isinstance(other, (list, tuple, set, frozenset)):
        for key, value in other:
            self[key] = value
    else:
        for key in other.keys():
            self[key] = other[key]


def _typename(x) -> str:
    # type(x).__name__ (Pystachy has it for exceptions): the types an operand may have
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, list):
        return "list"
    if isinstance(x, tuple):
        return "tuple"
    if isinstance(x, set):
        return "set"
    if isinstance(x, frozenset):
        return "frozenset"
    return type(x).__name__


def _dict_eq(data, other) -> bool:
    # data == other, of a mapping's items (data, a dict) and an operand whose own __eq__ returned
    # NotImplemented, as dict_richcompare answers then: the items of a dict or another of these
    # mappings, in any order; any other object (None) is not equal (CPython's identity test)
    if isinstance(other, dict):
        return data == other
    if isinstance(other, (defaultdict, OrderedDict, Counter)):
        return data == other._dict()
    return False


def _or_error(cls: str, other) -> str:
    # Pystachy port: CPython's | of a defaultdict or OrderedDict (defdict_or, odict_or) returns
    # NotImplemented unless other is a dict: its TypeError's message, for None and the builtin
    # types that are no mapping (an object of another class is read as a mapping, as by update)
    if other is None:
        return f"unsupported operand type(s) for |: '{cls}' and 'NoneType'"
    if isinstance(other, (bool, int, float, str, list, tuple, set, frozenset)):
        return f"unsupported operand type(s) for |: '{cls}' and '{_typename(other)}'"
    return ""


def _factory_repr(factory) -> str:
    # repr(default_factory) of a defaultdict: a builtin class's, as CPython's; a function's or a
    # Callable's has no address here
    if factory is None:
        return "None"
    if isinstance(factory, type):
        return f"<class '{factory.__name__}'>"
    return "<function>"


################################################################################
### defaultdict
################################################################################

class defaultdict(Generic[_KT, _VT]):
    """defaultdict(default_factory=None, /, [...]) --> dict with default factory

    The default factory is called without arguments to produce
    a new value when a key is not present, in __getitem__ only.
    A defaultdict compares equal to a dict with the same items.
    All remaining arguments are treated the same as if they were
    passed to the dict constructor, including keyword arguments.
    """

    def __init__(self, default_factory: Callable[[], _VT] | None = None,
                 other: "Iterable[tuple[_KT, _VT]] | dict[_KT, _VT] | defaultdict[_KT, _VT] | OrderedDict[_KT, _VT] | Counter[_KT]" = (),
                 /) -> None:
        # (the items are a dict's, and keyword arguments are not taken: an annotation such as
        # defaultdict[str, int] names the types)
        self.default_factory: Callable[[], _VT] | None = default_factory
        # (the factory given and its repr, which a Callable no longer has)
        self._made = self.default_factory
        self._shown = _factory_repr(default_factory)
        # (made once, as by dict.__new__: calling __init__ again updates the items)
        if not hasattr(self, "_data"):
            self._data: dict[_KT, _VT] = {}
        _update(self, other)

    def __missing__(self, key: _KT) -> _VT:
        """__missing__(key) # Called by __getitem__ for missing key; pseudo-code:
          if self.default_factory is None: raise KeyError((key,))
          self[key] = value = self.default_factory()
          return value
        """
        factory = self.default_factory
        if factory is None:
            raise KeyError(key)
        value = factory()
        # (PyDict_SetDefaultRef: a value that the factory stored for key stays)
        return self._data.setdefault(key, value)

    def __getitem__(self, key: _KT) -> _VT:
        if key in self._data:
            return self._data[key]
        return self.__missing__(key)

    def __setitem__(self, key: _KT, value: _VT) -> None:
        self._data[key] = value

    def __delitem__(self, key: _KT) -> None:
        del self._data[key]

    def __contains__(self, key: _KT) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[_KT]:
        # the keys when the loop starts (CPython's dict iterator raises RuntimeError when the dict
        # changes size)
        return iter(list(self._data))

    def __reversed__(self) -> Iterator[_KT]:
        """Return a reverse iterator over the dict keys."""
        return iter(list(reversed(self._data)))

    def keys(self) -> list[_KT]:
        return list(self._data)

    def values(self) -> list[_VT]:
        return list(self._data.values())

    def items(self) -> list[tuple[_KT, _VT]]:
        return list(self._data.items())

    def get(self, key: _KT, default=None):
        """Return the value for key if key is in the dictionary, else default."""
        return self._data.get(key, default)

    def setdefault(self, key: _KT, default: _VT) -> _VT:
        """Insert key with a value of default if key is not in the dictionary.

        Return the value for key if key is in the dictionary, else default.
        """
        return self._data.setdefault(key, default)

    def pop(self, key: _KT, *default):
        """D.pop(k[,d]) -> v, remove specified key and return the corresponding value.

        If the key is not found, return the default if given; otherwise,
        raise a KeyError.
        """
        if len(default) == 0:
            return self._data.pop(key)
        return self._data.pop(key, default[0])

    def popitem(self) -> tuple[_KT, _VT]:
        """Remove and return a (key, value) pair as a 2-tuple.

        Pairs are returned in LIFO (last-in, first-out) order.
        Raises KeyError if the dict is empty.
        """
        return self._data.popitem()

    def clear(self) -> None:
        """D.clear() -> None.  Remove all items from D."""
        self._data.clear()

    def _dict(self) -> dict[_KT, _VT]:
        return self._data

    def update(self, other=(), /, **kwds) -> None:
        """D.update([E, ]**F) -> None.  Update D from mapping/iterable E and F."""
        _update(self, other)
        if kwds:
            _update(self, dict(kwds))

    def copy(self) -> Self:
        """D.copy() -> a shallow copy of D."""
        new = defaultdict(self.default_factory, self)
        new._made = self._made
        new._shown = self._shown
        return new

    def __copy__(self) -> Self:
        """D.copy() -> a shallow copy of D."""
        return self.copy()

    def __eq__(self, other) -> bool:
        # (dict's: a dict or another mapping of the same items, in any order)
        return _dict_eq(self._data, other)

    def __ne__(self, other) -> bool:
        return not self == other

    def __or__(self, other) -> Self:
        if other is None or isinstance(other, (bool, int, float, str, list, tuple, set, frozenset)):
            raise TypeError(_or_error('collections.defaultdict', other))
        new = self.copy()
        _update(new, other)
        return new

    def __ior__(self, other):
        _update(self, other)
        return self

    def __repr__(self) -> str:
        factory = self.default_factory
        shown = "None"
        if factory is not None:
            made = self._made
            shown = self._shown if made is not None and factory == made else _factory_repr(factory)
        return f"defaultdict({shown}, {self._data!r})"


################################################################################
### OrderedDict
################################################################################

class OrderedDict(Generic[_KT, _VT]):
    'Dictionary that remembers insertion order'
    # Pystachy port: CPython's OrderedDict links its keys in a list. Here two dicts, which keep
    # their keys in insertion order, hold the items: _back the last ones, in order, and _front
    # the first ones, last first. Both ends of the order are thus ends of a dict, where an item
    # is added or removed in O(1); an end that a pop finds empty takes half of the other dict's
    # items, so that each operation takes amortized O(1) time, as with the linked list.

    def __init__(self, other: "Iterable[tuple[_KT, _VT]] | dict[_KT, _VT] | OrderedDict[_KT, _VT] | defaultdict[_KT, _VT] | Counter[_KT]" = (),
                 /) -> None:
        '''Initialize an ordered dictionary.  The signature is the same as
        regular dictionaries.  Keyword argument order is preserved.
        '''
        # (keyword arguments are not taken: an annotation such as OrderedDict[str, int] names
        # the types; the dicts are made once, as by dict.__new__: calling __init__ again updates
        # the items, as odict_init does)
        if not hasattr(self, "_front"):
            self._front: dict[_KT, _VT] = {}
        if not hasattr(self, "_back"):
            self._back: dict[_KT, _VT] = {}
        _update(self, other)

    def __setitem__(self, key: _KT, value: _VT) -> None:
        'od.__setitem__(i, y) <==> od[i]=y'
        if key in self._front:
            self._front[key] = value
        else:
            self._back[key] = value

    def __getitem__(self, key: _KT) -> _VT:
        if key in self._front:
            return self._front[key]
        return self._back[key]

    def __delitem__(self, key: _KT) -> None:
        'od.__delitem__(y) <==> del od[y]'
        if key in self._front:
            del self._front[key]
        else:
            del self._back[key]

    def __contains__(self, key: _KT) -> bool:
        return key in self._back or key in self._front

    def __len__(self) -> int:
        return len(self._front) + len(self._back)

    def __iter__(self) -> Iterator[_KT]:
        'od.__iter__() <==> iter(od)'
        # the keys when the loop starts (CPython's iterator raises RuntimeError when the
        # OrderedDict changes)
        return iter(self.keys())

    def __reversed__(self) -> Iterator[_KT]:
        'od.__reversed__() <==> reversed(od)'
        return iter(list(reversed(self._back)) + list(self._front))

    def clear(self) -> None:
        'od.clear() -> None.  Remove all items from od.'
        self._front.clear()
        self._back.clear()

    def popitem(self, last: bool = True) -> tuple[_KT, _VT]:
        '''Remove and return a (key, value) pair from the dictionary.

        Pairs are returned in LIFO order if last is true or FIFO order if false.
        '''
        if not self:
            raise KeyError('dictionary is empty')
        if last:
            if not self._back:
                self._split(len(self._front) // 2)
            return self._back.popitem()
        if not self._front:
            self._split((len(self._back) + 1) // 2)
        return self._front.popitem()

    def _split(self, n: int) -> None:
        # (the first n items to _front, the others to _back)
        items = self.items()
        front: dict[_KT, _VT] = {}
        for i in range(n - 1, -1, -1):
            front[items[i][0]] = items[i][1]
        back: dict[_KT, _VT] = {}
        for i in range(n, len(items)):
            back[items[i][0]] = items[i][1]
        self._front = front
        self._back = back

    def move_to_end(self, key: _KT, last: bool = True) -> None:
        '''Move an existing element to the end (or beginning if last is false).

        Raise KeyError if the element does not exist.
        '''
        if key in self._front:
            value = self._front.pop(key)
        else:
            value = self._back.pop(key)
        if last:
            self._back[key] = value
        else:
            self._front[key] = value

    def keys(self) -> list[_KT]:
        "D.keys() -> a set-like object providing a view on D's keys"
        return list(reversed(self._front)) + list(self._back)

    def items(self) -> list[tuple[_KT, _VT]]:
        "D.items() -> a set-like object providing a view on D's items"
        return list(reversed(self._front.items())) + list(self._back.items())

    def values(self) -> list[_VT]:
        "D.values() -> an object providing a view on D's values"
        return list(reversed(self._front.values())) + list(self._back.values())

    def update(self, other=(), /, **kwds) -> None:
        "D.update([E, ]**F) -> None.  Update D from mapping/iterable E and F."
        _update(self, other)
        if kwds:
            _update(self, dict(kwds))

    def get(self, key: _KT, default=None):
        'Return the value for key if key is in the dictionary, else default.'
        if key in self._front:
            return self._front.get(key, default)
        return self._back.get(key, default)

    def pop(self, key: _KT, *default):
        '''od.pop(key[,default]) -> v, remove specified key and return the corresponding value.

        If the key is not found, return the default if given; otherwise,
        raise a KeyError.
        '''
        data = self._front if key in self._front else self._back
        if len(default) == 0:
            return data.pop(key)
        return data.pop(key, default[0])

    def setdefault(self, key: _KT, default: _VT) -> _VT:
        '''Insert key with a value of default if key is not in the dictionary.

        Return the value for key if key is in the dictionary, else default.
        '''
        if key in self._front:
            return self._front[key]
        return self._back.setdefault(key, default)

    def _dict(self) -> dict[_KT, _VT]:
        # (the items, in their order, in a dict)
        if not self._front:
            return self._back
        data: dict[_KT, _VT] = {}
        for key, value in self.items():
            data[key] = value
        return data

    def __repr__(self) -> str:
        'od.__repr__() <==> repr(od)'
        if not self:
            return 'OrderedDict()'
        return f'OrderedDict({self._dict()!r})'

    def copy(self) -> Self:
        'od.copy() -> a shallow copy of od'
        return OrderedDict(self)

    @classmethod
    def fromkeys(cls, iterable, value=None):
        '''Create a new ordered dictionary with keys from iterable and values set to value.
        '''
        # Pystachy port: from the pairs, whose value types the object (value=None, which types
        # nothing, is not supported)
        return cls([(key, value) for key in iterable])

    def __eq__(self, other) -> bool:
        '''od.__eq__(y) <==> od==y.  Comparison to another OD is order-sensitive
        while comparison to a regular mapping is order-insensitive.

        '''
        if isinstance(other, OrderedDict):
            return self._dict() == other._dict() and self.keys() == other.keys()
        return _dict_eq(self._dict(), other)

    def __ne__(self, other) -> bool:
        return not self == other

    def __ior__(self, other):
        self.update(other)
        return self

    def __or__(self, other) -> Self:
        if other is None or isinstance(other, (bool, int, float, str, list, tuple, set, frozenset)):
            raise TypeError(_or_error('collections.OrderedDict', other))
        new = OrderedDict(self)
        new.update(other)
        return new


################################################################################
### Counter
################################################################################

def _count_elements(mapping, iterable) -> None:
    'Tally elements from the iterable.'
    for elem in iterable:
        mapping[elem] = mapping.get(elem, 0) + 1


class Counter(Generic[_T]):
    '''Dict subclass for counting hashable items.  Sometimes called a bag
    or multiset.  Elements are stored as dictionary keys and their counts
    are stored as dictionary values.

    >>> c = Counter('abcdeabcdabcaba')  # count elements from a string

    >>> c.most_common(3)                # three most common elements
    [('a', 5), ('b', 4), ('c', 3)]
    >>> sorted(c)                       # list all unique elements
    ['a', 'b', 'c', 'd', 'e']
    >>> ''.join(sorted(c.elements()))   # list elements with repetitions
    'aaaaabbbbcccdde'
    >>> sum(c.values())                 # total of all counts
    15

    >>> c['a']                          # count of letter 'a'
    5
    >>> for elem in 'shazam':           # update counts from an iterable
    ...     c[elem] += 1                # by adding 1 to each element's count
    >>> c['a']                          # now there are seven 'a'
    7
    >>> del c['b']                      # remove all 'b'
    >>> c['b']                          # now there are zero 'b'
    0

    >>> d = Counter('simsalabim')       # make another counter
    >>> c.update(d)                     # add in the second counter
    >>> c['a']                          # now there are nine 'a'
    9

    >>> c.clear()                       # empty the counter
    >>> c
    Counter()

    Note:  If a count is set to zero or reduced to zero, it will remain
    in the counter until the entry is deleted or the counter is cleared:

    >>> c = Counter('aaabbc')
    >>> c['b'] -= 2                     # reduce the count of 'b' by two
    >>> c.most_common()                 # 'b' is still in, but its count is zero
    [('a', 3), ('c', 1), ('b', 0)]

    '''
    # Pystachy port: the counts are int values of a dict field (this class derives from no dict)

    def __init__(self, iterable: Iterable[_T] = (), /) -> None:
        '''Create a new, empty Counter object.  And if given, count elements
        from an input iterable.  Or, initialize the count from another mapping
        of elements to their counts.

        >>> c = Counter()                           # a new, empty counter
        >>> c = Counter('gallahad')                 # a new counter from an iterable
        >>> c = Counter({'a': 4, 'b': 2})           # a new counter from a mapping

        '''
        # (keyword arguments are not taken: an annotation such as Counter[str] names the type)
        # Pystachy port: super().__init__(), which keeps a dict's items: the dict field is made
        # once, as by dict.__new__, and calling __init__ again adds to the counts
        if not hasattr(self, "_data"):
            self._data: dict[_T, int] = {}
        self.update(iterable)

    def __missing__(self, key: _T) -> int:
        'The count of elements not in the Counter is zero.'
        # Needed so that self[missing_item] does not raise KeyError
        return 0

    def total(self) -> int:
        'Sum of the counts'
        return sum(self._data.values())

    def most_common(self, n: int | None = None) -> list[tuple[_T, int]]:
        '''List the n most common elements and their counts from the most
        common to the least.  If n is None, then list all element counts.

        >>> Counter('abracadabra').most_common(3)
        [('a', 5), ('b', 2), ('r', 2)]

        '''
        # Emulate Bag.sortedByCount from Smalltalk
        if n is None:
            return sorted(self._data.items(), key=_count, reverse=True)
        # Pystachy port: the first n of the sorted items, which heapq.nlargest gives
        if n <= 0:
            return []
        return sorted(self._data.items(), key=_count, reverse=True)[:n]

    def elements(self) -> list[_T]:
        '''Iterator over elements repeating each as many times as its count.

        >>> c = Counter('ABCABC')
        >>> sorted(c.elements())
        ['A', 'A', 'B', 'B', 'C', 'C']

        Knuth's example for prime factors of 1836:  2**2 * 3**3 * 17**1

        >>> import math
        >>> prime_factors = Counter({2: 2, 3: 3, 17: 1})
        >>> math.prod(prime_factors.elements())
        1836

        Note, if an element's count has been set to zero or is a negative
        number, elements() will ignore it.

        '''
        # Emulate Bag.do from Smalltalk and Multiset.begin from C++.
        # Pystachy port: a list of the elements (CPython's is an iterator)
        result: list[_T] = []
        for elem, count in self._data.items():
            for _ in range(count):
                result.append(elem)
        return result

    def update(self, iterable=None, /, **kwds) -> None:
        '''Like dict.update() but add counts instead of replacing them.

        Source can be an iterable, a dictionary, or another Counter instance.

        >>> c = Counter('which')
        >>> c.update('witch')           # add elements from another iterable
        >>> d = Counter('watch')
        >>> c.update(d)                 # add elements from another counter
        >>> c['h']                      # four 'h' in which, witch, and watch
        4

        '''
        # The regular dict.update() operation makes no sense here because the
        # replace behavior results in some of the original untouched counts
        # being mixed-in with all of the other counts for a mismash that
        # doesn't have a straight-forward interpretation in most counting
        # contexts.  Instead, we implement straight-addition.  Both the inputs
        # and outputs are allowed to contain zero and negative counts.

        if iterable is not None:
            # Pystachy port: the Mappings are dicts and this module's mapping classes
            if isinstance(iterable, dict) or isinstance(iterable, (Counter, OrderedDict, defaultdict)):
                if self:
                    for elem, count in iterable.items():
                        self[elem] = count + self.get(elem, 0)
                else:
                    # fast path when counter is empty
                    for elem, count in iterable.items():
                        self._data[elem] = count
            else:
                _count_elements(self, iterable)
        if kwds:
            self.update(dict(kwds))

    def subtract(self, iterable=None, /, **kwds) -> None:
        '''Like dict.update() but subtracts counts instead of replacing them.
        Counts can be reduced below zero.  Both the inputs and outputs are
        allowed to contain zero and negative counts.

        Source can be an iterable, a dictionary, or another Counter instance.

        >>> c = Counter('which')
        >>> c.subtract('witch')             # subtract elements from another iterable
        >>> c.subtract(Counter('watch'))    # subtract elements from another counter
        >>> c['h']                          # 2 in which, minus 1 in witch, minus 1 in watch
        0
        >>> c['w']                          # 1 in which, minus 1 in witch, minus 1 in watch
        -1

        '''
        if iterable is not None:
            if isinstance(iterable, dict) or isinstance(iterable, (Counter, OrderedDict, defaultdict)):
                for elem, count in iterable.items():
                    self[elem] = self.get(elem, 0) - count
            else:
                for elem in iterable:
                    self[elem] = self.get(elem, 0) - 1
        if kwds:
            self.subtract(dict(kwds))

    @classmethod
    def fromkeys(cls, iterable, v=None):
        # There is no equivalent method for counters because the semantics
        # would be ambiguous in cases such as Counter.fromkeys('aaabbc', v=2).
        # Initializing counters to zero values isn't necessary because zero
        # is already the default value for counter lookups.  Initializing
        # to one is easily accomplished with Counter(set(iterable)).  For
        # more exotic cases, create a dictionary first using a dictionary
        # comprehension or dict.fromkeys().
        raise NotImplementedError(
            'Counter.fromkeys() is undefined.  Use Counter(iterable) instead.')

    def copy(self) -> Self:
        'Return a shallow copy.'
        return Counter(self)

    def __getitem__(self, key: _T) -> int:
        # (dict's, which calls __missing__ for a missing key)
        if key in self._data:
            return self._data[key]
        return self.__missing__(key)

    def __setitem__(self, key: _T, value: int) -> None:
        self._data[key] = value

    def __delitem__(self, elem: _T) -> None:
        'Like dict.__delitem__() but does not raise KeyError for missing values.'
        if elem in self:
            del self._data[elem]

    def __contains__(self, key: _T) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[_T]:
        # the elements when the loop starts (CPython's dict iterator raises RuntimeError when
        # the dict changes size)
        return iter(list(self._data))

    def __reversed__(self) -> Iterator[_T]:
        """Return a reverse iterator over the dict keys."""
        return iter(list(reversed(self._data)))

    def keys(self) -> list[_T]:
        return list(self._data)

    def values(self) -> list[int]:
        return list(self._data.values())

    def items(self) -> list[tuple[_T, int]]:
        return list(self._data.items())

    def get(self, key: _T, default=None):
        """Return the value for key if key is in the dictionary, else default."""
        return self._data.get(key, default)

    def setdefault(self, key: _T, default: int) -> int:
        """Insert key with a value of default if key is not in the dictionary.

        Return the value for key if key is in the dictionary, else default.
        """
        return self._data.setdefault(key, default)

    def pop(self, key: _T, *default):
        """D.pop(k[,d]) -> v, remove specified key and return the corresponding value.

        If the key is not found, return the default if given; otherwise,
        raise a KeyError.
        """
        if len(default) == 0:
            return self._data.pop(key)
        return self._data.pop(key, default[0])

    def popitem(self) -> tuple[_T, int]:
        """Remove and return a (key, value) pair as a 2-tuple.

        Pairs are returned in LIFO (last-in, first-out) order.
        Raises KeyError if the dict is empty.
        """
        return self._data.popitem()

    def clear(self) -> None:
        """D.clear() -> None.  Remove all items from D."""
        self._data.clear()

    def _dict(self) -> dict[_T, int]:
        return self._data

    def __repr__(self) -> str:
        if not self:
            return 'Counter()'
        # dict() preserves the ordering returned by most_common()
        d: dict[_T, int] = {}
        for elem, count in self.most_common():
            d[elem] = count
        return f'Counter({d!r})'

    # Multiset-style mathematical operations discussed in:
    #       Knuth TAOCP Volume II section 4.6.3 exercise 19
    #       and at http://en.wikipedia.org/wiki/Multiset
    #
    # Outputs guaranteed to only include positive counts.
    #
    # To strip negative and zero counts, add-in an empty counter:
    #       c += Counter()
    #
    # Results are ordered according to when an element is first
    # encountered in the left operand and then by the order
    # encountered in the right operand.
    #
    # When the multiplicities are all zero or one, multiset operations
    # are guaranteed to be equivalent to the corresponding operations
    # for regular sets.

    def __eq__(self, other) -> bool:
        'True if all counts agree. Missing counts are treated as zero.'
        if not isinstance(other, Counter):
            # Pystachy port: NotImplemented, after which CPython compares a dict's items
            return _dict_eq(self._data, other)
        return all([self[e] == other[e] for e in self]) and all([self[e] == other[e] for e in other])

    def __ne__(self, other) -> bool:
        'True if any counts disagree. Missing counts are treated as zero.'
        return not self == other

    def __le__(self, other: Self) -> bool:
        'True if all counts in self are a subset of those in other.'
        if not isinstance(other, Counter):
            # Pystachy port: NotImplemented, which makes CPython's TypeError (other is None)
            raise TypeError("'<=' not supported between instances of 'Counter' and 'NoneType'")
        return all([self[e] <= other[e] for e in self]) and all([self[e] <= other[e] for e in other])

    def __lt__(self, other: Self) -> bool:
        'True if all counts in self are a proper subset of those in other.'
        if not isinstance(other, Counter):
            # Pystachy port: NotImplemented, which makes CPython's TypeError (other is None)
            raise TypeError("'<' not supported between instances of 'Counter' and 'NoneType'")
        return self <= other and self != other

    def __ge__(self, other: Self) -> bool:
        'True if all counts in self are a superset of those in other.'
        if not isinstance(other, Counter):
            # Pystachy port: NotImplemented, which makes CPython's TypeError (other is None)
            raise TypeError("'>=' not supported between instances of 'Counter' and 'NoneType'")
        return all([self[e] >= other[e] for e in self]) and all([self[e] >= other[e] for e in other])

    def __gt__(self, other: Self) -> bool:
        'True if all counts in self are a proper superset of those in other.'
        if not isinstance(other, Counter):
            # Pystachy port: NotImplemented, which makes CPython's TypeError (other is None)
            raise TypeError("'>' not supported between instances of 'Counter' and 'NoneType'")
        return self >= other and self != other

    def __add__(self, other: Self) -> Self:
        '''Add counts from two counters.

        >>> Counter('abbb') + Counter('bcc')
        Counter({'b': 4, 'c': 2, 'a': 1})

        '''
        if not isinstance(other, Counter):
            # Pystachy port: NotImplemented, which makes CPython's TypeError (other is None)
            raise TypeError("unsupported operand type(s) for +: 'Counter' and 'NoneType'")
        result: Counter[_T] = Counter()
        for elem, count in self.items():
            newcount = count + other[elem]
            if newcount > 0:
                result[elem] = newcount
        for elem, count in other.items():
            if elem not in self and count > 0:
                result[elem] = count
        return result

    def __sub__(self, other: Self) -> Self:
        ''' Subtract count, but keep only results with positive counts.

        >>> Counter('abbbc') - Counter('bccd')
        Counter({'b': 2, 'a': 1})

        '''
        if not isinstance(other, Counter):
            # Pystachy port: NotImplemented, which makes CPython's TypeError (other is None)
            raise TypeError("unsupported operand type(s) for -: 'Counter' and 'NoneType'")
        result: Counter[_T] = Counter()
        for elem, count in self.items():
            newcount = count - other[elem]
            if newcount > 0:
                result[elem] = newcount
        for elem, count in other.items():
            if elem not in self and count < 0:
                result[elem] = 0 - count
        return result

    def __or__(self, other: Self) -> Self:
        '''Union is the maximum of value in either of the input counters.

        >>> Counter('abbb') | Counter('bcc')
        Counter({'b': 3, 'c': 2, 'a': 1})

        '''
        if not isinstance(other, Counter):
            # Pystachy port: NotImplemented, which makes CPython's TypeError (other is None)
            raise TypeError("unsupported operand type(s) for |: 'Counter' and 'NoneType'")
        result: Counter[_T] = Counter()
        for elem, count in self.items():
            other_count = other[elem]
            newcount = other_count if count < other_count else count
            if newcount > 0:
                result[elem] = newcount
        for elem, count in other.items():
            if elem not in self and count > 0:
                result[elem] = count
        return result

    def __and__(self, other: Self) -> Self:
        ''' Intersection is the minimum of corresponding counts.

        >>> Counter('abbb') & Counter('bcc')
        Counter({'b': 1})

        '''
        if not isinstance(other, Counter):
            # Pystachy port: NotImplemented, which makes CPython's TypeError (other is None)
            raise TypeError("unsupported operand type(s) for &: 'Counter' and 'NoneType'")
        result: Counter[_T] = Counter()
        for elem, count in self.items():
            other_count = other[elem]
            newcount = count if count < other_count else other_count
            if newcount > 0:
                result[elem] = newcount
        return result

    def __pos__(self) -> Self:
        'Adds an empty counter, effectively stripping negative and zero counts'
        result: Counter[_T] = Counter()
        for elem, count in self.items():
            if count > 0:
                result[elem] = count
        return result

    def __neg__(self) -> Self:
        '''Subtracts from an empty counter.  Strips positive and zero counts,
        and flips the sign on negative counts.

        '''
        result: Counter[_T] = Counter()
        for elem, count in self.items():
            if count < 0:
                result[elem] = 0 - count
        return result

    def _keep_positive(self) -> Self:
        '''Internal method to strip elements with a negative or zero count'''
        nonpositive = [elem for elem, count in self.items() if not count > 0]
        for elem in nonpositive:
            del self[elem]
        return self

    def __iadd__(self, other: Self) -> Self:
        '''Inplace add from another counter, keeping only positive counts.

        >>> c = Counter('abbb')
        >>> c += Counter('bcc')
        >>> c
        Counter({'b': 4, 'c': 2, 'a': 1})

        '''
        for elem, count in other.items():
            self[elem] += count
        return self._keep_positive()

    def __isub__(self, other: Self) -> Self:
        '''Inplace subtract counter, but keep only results with positive counts.

        >>> c = Counter('abbbc')
        >>> c -= Counter('bccd')
        >>> c
        Counter({'b': 2, 'a': 1})

        '''
        for elem, count in other.items():
            self[elem] -= count
        return self._keep_positive()

    def __ior__(self, other: Self) -> Self:
        '''Inplace union is the maximum of value from either counter.

        >>> c = Counter('abbb')
        >>> c |= Counter('bcc')
        >>> c
        Counter({'b': 3, 'c': 2, 'a': 1})

        '''
        for elem, other_count in other.items():
            count = self[elem]
            if other_count > count:
                self[elem] = other_count
        return self._keep_positive()

    def __iand__(self, other: Self) -> Self:
        '''Inplace intersection is the minimum of corresponding counts.

        >>> c = Counter('abbb')
        >>> c &= Counter('bcc')
        >>> c
        Counter({'b': 1})

        '''
        for elem, count in self.items():
            other_count = other[elem]
            if other_count < count:
                self[elem] = other_count
        return self._keep_positive()


def _count(item: tuple[_T, int]) -> int:
    # (operator.itemgetter(1), most_common's key)
    return item[1]
class _deque_iterator:
    def __init__(self, source):
        self._source = source
        self._state: int = source._state
        self._index = 0
        self._remaining: int = len(source)

    def __iter__(self):
        return self

    def __next__(self):
        if self._source._state != self._state:
            self._remaining = 0
            raise RuntimeError("deque mutated during iteration")
        if self._remaining == 0:
            raise StopIteration
        value = self._source[self._index]
        self._index += 1
        self._remaining -= 1
        return value
