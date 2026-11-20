"""Abstract Base Classes (ABCs) for collections, according to PEP 3119.

Unit tests are in test_collections.
"""
# The classes of collections.abc that a class of the program derives from: CPython 3.13.16's
# _collections_abc.py, changed where a "Pystachy port:" comment says. A class statement whose
# base names one of them (collections.abc's or typing's name, subscripted or not) derives from
# this module's class instead (Loader's abc_classes), whose methods it inherits, as CPython's
# subclasses do; the compiler decides isinstance() and issubclass() with each ABC itself
# (Gen.cabc_isinst), for the program's values and for these classes' objects alike, where
# CPython asks the ABC's __subclasshook__ and its registry. Elsewhere collections.abc's names
# stay the types they annotate (Mapping[K, V] is dict[K, V]). The docstrings are CPython's.
#
# Pystachy port: each class derives from one class. CPython's Collection derives from Sized,
# Iterable and Container, Sequence from Reversible and Collection too, and the views from
# MappingView and Set (or Collection): here Collection declares the three abstract methods
# itself, and the views have MappingView's and Set's methods. The compiler's isinstance()
# answers as CPython's does for these classes all the same. No __subclasshook__,
# __class_getitem__ (a base's subscript is dropped where the class derives from it) or
# register() (the compiler knows the classes CPython registers).
from abc import ABCMeta, abstractmethod


### ONE-TRICK PONIES ###

class Hashable(metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    def __hash__(self):
        return 0


class Iterable(metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    def __iter__(self):
        while False:
            yield None


class Iterator(Iterable):

    __slots__ = ()

    @abstractmethod
    def __next__(self):
        'Return the next item from the iterator. When exhausted, raise StopIteration'
        raise StopIteration

    def __iter__(self):
        return self


class Reversible(Iterable):

    __slots__ = ()

    @abstractmethod
    def __reversed__(self):
        while False:
            yield None


class Sized(metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    def __len__(self):
        return 0


class Container(metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    def __contains__(self, x):
        return False


class Collection(metaclass=ABCMeta):  # Pystachy port: was Collection(Sized, Iterable, Container)

    __slots__ = ()

    # Pystachy port: Sized's, Iterable's and Container's abstract methods, which CPython's inherits
    @abstractmethod
    def __len__(self):
        return 0

    @abstractmethod
    def __iter__(self):
        while False:
            yield None

    @abstractmethod
    def __contains__(self, x):
        return False


def _chain(a, b):
    # Pystachy port: Set.__or__'s chain, (e for s in (self, other) for e in s), whose s would be
    # two types
    for e in a:
        yield e
    for e in b:
        yield e


def _unsupported(op, a, b):
    # Pystachy port: the TypeError of operator op where Set's method would return NotImplemented
    # (only comparisons return it here): CPython's, where the other operand's reflected method,
    # if it has one, returns NotImplemented too
    return TypeError(f"unsupported operand type(s) for {op}: '{type(a).__name__}' and '{type(b).__name__}'")


### SETS ###

# Pystachy port: what Set's methods do past their test of the other operand, as functions, which
# KeysView's and ItemsView's methods call too (CPython's derive from Set: here they derive from
# no class, see KeysView). Only comparisons return NotImplemented here: the other operators raise
# the TypeError that CPython's then raises (_unsupported)

def _le(self, other):
    if len(self) > len(other):
        return False
    for elem in self:
        if elem not in other:
            return False
    return True


def _ge(self, other):
    if len(self) < len(other):
        return False
    for elem in other:
        if elem not in self:
            return False
    return True


def _and(self, other, op_self, op_other):
    if not isinstance(other, Iterable):
        raise _unsupported("&", op_self, op_other)
    return self._from_iterable(value for value in other if value in self)


def _isdisjoint(self, other):
    for value in other:
        if value in self:
            return False
    return True


def _or(self, other, op_self, op_other):
    if not isinstance(other, Iterable):
        raise _unsupported("|", op_self, op_other)
    chain = _chain(self, other)  # Pystachy port: see _chain
    return self._from_iterable(chain)


def _sub(self, other):
    if not isinstance(other, Set):
        if not isinstance(other, Iterable):
            raise _unsupported("-", self, other)
        # Pystachy port: a new variable, where CPython's rebinds other (a parameter keeps its type)
        made = self._from_iterable(other)
        return self._from_iterable(value for value in self
                                   if value not in made)
    return self._from_iterable(value for value in self
                               if value not in other)


def _rsub(self, other):
    if not isinstance(other, Set):
        if not isinstance(other, Iterable):
            raise _unsupported("-", other, self)
        made = self._from_iterable(other)  # Pystachy port: see _sub
        return self._from_iterable(value for value in made
                                   if value not in self)
    return self._from_iterable(value for value in other
                               if value not in self)


def _xor(self, other, op_self, op_other):
    if not isinstance(other, Set):
        if not isinstance(other, Iterable):
            raise _unsupported("^", op_self, op_other)
        made = self._from_iterable(other)  # Pystachy port: see _sub
        return _xor_set(self, made)
    return _xor_set(self, other)


def _xor_set(self, other):
    # (self - other) | (other - self), for a set-like other
    if isinstance(other, set) or isinstance(other, frozenset):
        # Pystachy port: other - self, which CPython's set.__sub__ leaves to self's __rsub__
        return (self - other) | _rsub(self, other)
    return (self - other) | (other - self)


class Set(Collection):
    """A set is a finite, iterable container.

    This class provides concrete generic implementations of all
    methods except for __contains__, __iter__ and __len__.

    To override the comparisons (presumably for speed, as the
    semantics are fixed), redefine __le__ and __ge__,
    then the other operations will automatically follow suit.
    """

    __slots__ = ()

    def __le__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return _le(self, other)

    def __lt__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) < len(other) and self.__le__(other)

    def __gt__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) > len(other) and self.__ge__(other)

    def __ge__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return _ge(self, other)

    def __eq__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) == len(other) and self.__le__(other)

    # Pystachy port: an instance method, which makes an object of the object's own class: a class
    # method that uses cls is compiled for the class defining it alone, where a class of another
    # module inherits it (a subclass overrides it with a method, not a class method)
    def _from_iterable(self, it):
        '''Construct an instance of the class from any iterable input.

        Must override this method if the class constructor signature
        does not accept an iterable for an input.
        '''
        return type(self)(it)

    def __and__(self, other):
        return _and(self, other, self, other)

    def __rand__(self, other):  # Pystachy port: was __rand__ = __and__
        return _and(self, other, other, self)

    def isdisjoint(self, other):
        'Return True if two sets have a null intersection.'
        return _isdisjoint(self, other)

    def __or__(self, other):
        return _or(self, other, self, other)

    def __ror__(self, other):  # Pystachy port: was __ror__ = __or__
        return _or(self, other, other, self)

    def __sub__(self, other):
        return _sub(self, other)

    def __rsub__(self, other):
        return _rsub(self, other)

    def __xor__(self, other):
        return _xor(self, other, self, other)

    def __rxor__(self, other):  # Pystachy port: was __rxor__ = __xor__
        return _xor(self, other, other, self)

    # Pystachy port: no _hash(), whose arithmetic needs ints past 64 bits


class MutableSet(Set):
    """A mutable set is a finite, iterable container.

    This class provides concrete generic implementations of all
    methods except for __contains__, __iter__, __len__,
    add(), and discard().

    To override the comparisons (presumably for speed, as the
    semantics are fixed), all you have to do is redefine __le__ and
    then the other operations will automatically follow suit.
    """

    __slots__ = ()

    @abstractmethod
    def add(self, value):
        """Add an element."""
        raise NotImplementedError

    @abstractmethod
    def discard(self, value):
        """Remove an element.  Do not raise an exception if absent."""
        raise NotImplementedError

    def remove(self, value):
        """Remove an element. If not a member, raise a KeyError."""
        if value not in self:
            raise KeyError(value)
        self.discard(value)

    def pop(self):
        """Return the popped value.  Raise KeyError if empty."""
        it = iter(self)
        try:
            value = next(it)
        except StopIteration:
            raise KeyError from None
        self.discard(value)
        return value

    def clear(self):
        """This is slow (creates N new iterators!) but effective."""
        try:
            while True:
                self.pop()
        except KeyError:
            pass

    def __ior__(self, it):
        for value in it:
            self.add(value)
        return self

    def __iand__(self, it):
        for value in (self - it):
            self.discard(value)
        return self

    def __ixor__(self, it):
        if it is self:
            self.clear()
        else:
            if not isinstance(it, Set):
                it_set = self._from_iterable(it)  # Pystachy port: see _sub
                for value in it_set:
                    if value in self:
                        self.discard(value)
                    else:
                        self.add(value)
                return self
            for value in it:
                if value in self:
                    self.discard(value)
                else:
                    self.add(value)
        return self

    def __isub__(self, it):
        if it is self:
            self.clear()
        else:
            for value in it:
                self.discard(value)
        return self


### MAPPINGS ###

class Mapping(Collection):
    """A Mapping is a generic container for associating key/value
    pairs.

    This class provides concrete generic implementations of all
    methods except for __getitem__, __iter__, and __len__.
    """

    __slots__ = ()

    @abstractmethod
    def __getitem__(self, key):
        raise KeyError

    def get(self, key, default=None):
        'D.get(k[,d]) -> D[k] if k in D, else d.  d defaults to None.'
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True

    def keys(self):
        "D.keys() -> a set-like object providing a view on D's keys"
        return KeysView(self)

    def items(self):
        "D.items() -> a set-like object providing a view on D's items"
        return ItemsView(self)

    def values(self):
        "D.values() -> an object providing a view on D's values"
        return ValuesView(self)

    def __eq__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        # Pystachy port: comprehensions, where CPython's dict() takes the views' pairs
        return {k: v for k, v in self.items()} == {k: v for k, v in other.items()}

    # Pystachy port: no __reversed__ = None: reversed() of a Mapping is a compile-time error (no
    # __reversed__ to call), where CPython's raises TypeError


class MappingView:  # Pystachy port: was MappingView(Sized)

    __slots__ = '_mapping',

    def __init__(self, mapping):
        self._mapping = mapping

    def __len__(self):
        return len(self._mapping)

    def __repr__(self):
        return f"{type(self).__name__}({self._mapping!r})"  # Pystachy port: was '{0.__class__.__name__}({0._mapping!r})'.format(self)


# Pystachy port: KeysView and ItemsView derive from no class: CPython's derive from MappingView
# and Set, whose methods they have here (a view is a class template, which no class derives from)

class KeysView:

    __slots__ = '_mapping',

    def __init__(self, mapping):
        self._mapping = mapping

    def __len__(self):
        return len(self._mapping)

    def __repr__(self):
        return f"{type(self).__name__}({self._mapping!r})"

    def _from_iterable(self, it):  # Pystachy port: an instance method, as Set's
        return set(it)

    def __contains__(self, key):
        return key in self._mapping

    def __iter__(self):
        yield from self._mapping

    # Pystachy port: Set's methods (see _le)
    def __le__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return _le(self, other)

    def __lt__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) < len(other) and self.__le__(other)

    def __gt__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) > len(other) and self.__ge__(other)

    def __ge__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return _ge(self, other)

    def __eq__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) == len(other) and self.__le__(other)

    def __and__(self, other):
        return _and(self, other, self, other)

    def __rand__(self, other):
        return _and(self, other, other, self)

    def isdisjoint(self, other):
        'Return True if two sets have a null intersection.'
        return _isdisjoint(self, other)

    def __or__(self, other):
        return _or(self, other, self, other)

    def __ror__(self, other):
        return _or(self, other, other, self)

    def __sub__(self, other):
        return _sub(self, other)

    def __rsub__(self, other):
        return _rsub(self, other)

    def __xor__(self, other):
        return _xor(self, other, self, other)

    def __rxor__(self, other):
        return _xor(self, other, other, self)


class ItemsView:

    __slots__ = '_mapping',

    def __init__(self, mapping):
        self._mapping = mapping

    def __len__(self):
        return len(self._mapping)

    def __repr__(self):
        return f"{type(self).__name__}({self._mapping!r})"

    def _from_iterable(self, it):  # Pystachy port: an instance method, as Set's
        return set(it)

    def __contains__(self, item):
        key, value = item
        try:
            v = self._mapping[key]
        except KeyError:
            return False
        else:
            return v is value or v == value

    def __iter__(self):
        for key in self._mapping:
            yield (key, self._mapping[key])

    # Pystachy port: Set's methods (see _le)
    def __le__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return _le(self, other)

    def __lt__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) < len(other) and self.__le__(other)

    def __gt__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) > len(other) and self.__ge__(other)

    def __ge__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return _ge(self, other)

    def __eq__(self, other):
        if not isinstance(other, Set):
            return NotImplemented
        return len(self) == len(other) and self.__le__(other)

    def __and__(self, other):
        return _and(self, other, self, other)

    def __rand__(self, other):
        return _and(self, other, other, self)

    def isdisjoint(self, other):
        'Return True if two sets have a null intersection.'
        return _isdisjoint(self, other)

    def __or__(self, other):
        return _or(self, other, self, other)

    def __ror__(self, other):
        return _or(self, other, other, self)

    def __sub__(self, other):
        return _sub(self, other)

    def __rsub__(self, other):
        return _rsub(self, other)

    def __xor__(self, other):
        return _xor(self, other, self, other)

    def __rxor__(self, other):
        return _xor(self, other, other, self)


class ValuesView:  # Pystachy port: was ValuesView(MappingView, Collection)

    __slots__ = '_mapping',

    def __init__(self, mapping):
        self._mapping = mapping

    def __len__(self):
        return len(self._mapping)

    def __repr__(self):
        return f"{type(self).__name__}({self._mapping!r})"

    def __contains__(self, value):
        for key in self._mapping:
            v = self._mapping[key]
            if v is value or v == value:
                return True
        return False

    def __iter__(self):
        for key in self._mapping:
            yield self._mapping[key]


class MutableMapping(Mapping):
    """A MutableMapping is a generic container for associating
    key/value pairs.

    This class provides concrete generic implementations of all
    methods except for __getitem__, __setitem__, __delitem__,
    __iter__, and __len__.
    """

    __slots__ = ()

    @abstractmethod
    def __setitem__(self, key, value):
        raise KeyError

    @abstractmethod
    def __delitem__(self, key):
        raise KeyError

    # Pystachy port: no __marker = object(): pop() takes its default as *default, whose
    # length tells whether it was given (a call cannot name it default=)
    def pop(self, key, *default):
        '''D.pop(k[,d]) -> v, remove specified key and return the corresponding
        value.  If key is not found, d is returned if given, otherwise
        KeyError is raised.
        '''
        if len(default) == 0:
            value = self[key]
            del self[key]
            return value
        try:
            value = self[key]
        except KeyError:
            return default[0]
        else:
            del self[key]
            return value

    def popitem(self):
        '''D.popitem() -> (k, v), remove and return some (key, value) pair
           as a 2-tuple; but raise KeyError if D is empty.
        '''
        try:
            key = next(iter(self))
        except StopIteration:
            raise KeyError from None
        value = self[key]
        del self[key]
        return key, value

    def clear(self):
        'D.clear() -> None.  Remove all items from D.'
        try:
            while True:
                self.popitem()
        except KeyError:
            pass

    def update(self, other=(), /, **kwds):
        ''' D.update([E, ]**F) -> None.  Update D from mapping/iterable E and F.
            If E present and has a .keys() method, does:
                for k in E.keys(): D[k] = E[k]
            If E present and lacks .keys() method, does:
                for (k, v) in E: D[k] = v
            In either case, this is followed by:
                for k, v in F.items(): D[k] = v
        '''
        # Pystachy port: the branches by the type of other, each compiled where a value of that
        # type may take it (an object may be None): pairs come from a list, tuple, set or
        # frozenset, where CPython's take them from any iterable without keys(), and an object is
        # a mapping or has keys(); None raises the TypeError of CPython's loop over the pairs
        if other is None:
            raise TypeError("'NoneType' object is not iterable")
        if isinstance(other, list) or isinstance(other, tuple) or isinstance(other, set) or isinstance(other, frozenset):
            for key, value in other:
                self[key] = value
        elif isinstance(other, Mapping):
            for key in other:
                self[key] = other[key]
        else:
            for key in other.keys():
                self[key] = other[key]
        for key, value in kwds.items():
            self[key] = value

    def setdefault(self, key, default=None):
        'D.setdefault(k[,d]) -> D.get(k,d), also set D[k]=d if k not in D'
        try:
            return self[key]
        except KeyError:
            self[key] = default
        return default


### SEQUENCES ###

class Sequence(Collection):  # Pystachy port: was Sequence(Reversible, Collection)
    """All the operations on a read-only sequence.

    Concrete subclasses must override __new__ or __init__,
    __getitem__, and __len__.
    """

    __slots__ = ()

    @abstractmethod
    def __getitem__(self, index):
        raise IndexError

    def __iter__(self):
        i = 0
        try:
            while True:
                v = self[i]
                yield v
                i += 1
        except IndexError:
            return

    def __contains__(self, value):
        for v in self:
            if v is value or v == value:
                return True
        return False

    def __reversed__(self):
        for i in reversed(range(len(self))):
            yield self[i]

    def index(self, value, start=0, stop=None):
        '''S.index(value, [start, [stop]]) -> integer -- return first index of
           value.  Raises ValueError if the value is not present.

           Supporting start and stop arguments is optional, but
           recommended.
        '''
        if start is not None and start < 0:
            start = max(len(self) + start, 0)
        if stop is not None and stop < 0:
            stop += len(self)

        i = start
        while stop is None or i < stop:
            try:
                v = self[i]
            except IndexError:
                break
            if v is value or v == value:
                return i
            i += 1
        raise ValueError

    def count(self, value):
        'S.count(value) -> integer -- return number of occurrences of value'
        return sum(1 for v in self if v is value or v == value)


class MutableSequence(Sequence):
    """All the operations on a read-write sequence.

    Concrete subclasses must provide __new__ or __init__,
    __getitem__, __setitem__, __delitem__, __len__, and insert().
    """

    __slots__ = ()

    @abstractmethod
    def __setitem__(self, index, value):
        raise IndexError

    @abstractmethod
    def __delitem__(self, index):
        raise IndexError

    @abstractmethod
    def insert(self, index, value):
        'S.insert(index, value) -- insert value before index'
        raise IndexError

    def append(self, value):
        'S.append(value) -- append value to the end of the sequence'
        self.insert(len(self), value)

    def clear(self):
        'S.clear() -> None -- remove all items from S'
        try:
            while True:
                self.pop()
        except IndexError:
            pass

    def reverse(self):
        'S.reverse() -- reverse *IN PLACE*'
        n = len(self)
        for i in range(n//2):
            self[i], self[n-i-1] = self[n-i-1], self[i]

    def extend(self, values):
        """S.extend(iterable) -- extend sequence by appending elements from the
        iterable"""
        if values is self:
            values = list(values)
        for v in values:
            self.append(v)

    def pop(self, index=-1):
        '''S.pop([index]) -> item -- remove and return item at index (default
        last).  Raise IndexError if list is empty or index is out of range.
        '''
        v = self[index]
        del self[index]
        return v

    def remove(self, value):
        '''S.remove(value) -- remove first occurrence of value.
           Raise ValueError if the value is not present.
        '''
        del self[self.index(value)]

    def __iadd__(self, values):
        self.extend(values)
        return self
