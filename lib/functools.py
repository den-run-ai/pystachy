"""functools for Pystachy: caching, reduction and comparison keys.

reduce() and cmp_to_key() adapt the Python fallback algorithms from CPython
3.13.16 Lib/functools.py, commit cbc944f4bc59639a444dd971c737788ba2283a91,
SHA-256 c95756a4d9bfb159e9cbda243f9d62b0d10860bb68f9a5a37880d3cae44b2175.
Their subset specializations require fixed accumulator/key types. Both adapted
algorithms also run under CPython; tests compare compiled execution separately
with CPython's native public implementations.

Pystachy's own stand-in for CPython 3.13's Lib/functools.py, whose lru_cache() wraps the C type
_functools._lru_cache_wrapper (Modules/_functoolsmodule.c). The wrapper below follows that C code:
the same three behaviours by maxsize (no caching, unbounded, least recently used), the same
statistics, and the same order of lookups, calls and updates, so a function that calls itself or
clears its own cache sees what it sees under CPython.

A Pystachy dict holds keys of one type and values of another, so each decorated function gets a
cache of its own types: _lru_cache_wrapper is a generic class, Generic[*_Ts, _R], whose __init__
takes the function as a Callable[[*_Ts], _R]. Each object binds _Ts to the function's parameter
types and _R to its return type (docs/language.md, *Typing rules*). The compiler binds defaults
and keyword arguments against the original function and adds a static call-shape tag, so
different ways to supply the same values keep distinct cache entries. Full positional keys
remain tuple[*_Ts]; other forms use (shape, tuple[*_Ts]) in a second map into the same LRU.

When this module runs under CPython, the public decorators use its native _functools wrapper.
"""

from typing import Callable, Generic, NamedTuple, TypeVar, TypeVarTuple

__all__ = ["cache", "lru_cache", "reduce", "cmp_to_key"]

_Ts = TypeVarTuple("_Ts")  # the decorated function's parameter types
_R = TypeVar("_R")  # and its return type
_T = TypeVar("_T")
_F = TypeVar("_F")


class _CmpKey(Generic[_T, _F]):
    # Pystachy port: CPython's cmp_to_key() Python fallback defines its K class
    # inside the function and closes over mycmp. Classes must be module-level
    # in the subset, so a typed field carries that same comparator.
    def __init__(self, obj: _T, mycmp: _F) -> None:
        self.obj = obj
        self._cmp = mycmp

    def _compare(self, other) -> int:
        # The native public wrapper rejects an unrelated object even when it
        # happens to expose .obj; the Python fallback's duck typing does not.
        if not isinstance(other, _CmpKey):
            raise TypeError("other argument must be K instance")
        return self._cmp(self.obj, other.obj)

    def __lt__(self, other) -> bool:
        return self._compare(other) < 0

    def __gt__(self, other) -> bool:
        return self._compare(other) > 0

    def __eq__(self, other) -> bool:
        return self._compare(other) == 0

    def __le__(self, other) -> bool:
        return self._compare(other) <= 0

    def __ge__(self, other) -> bool:
        return self._compare(other) >= 0

    # Pystachy port: defining __eq__ disables __hash__ under CPython without
    # an explicit None class attribute (unsupported in the subset). Pystachy
    # rejects hash() on user-class instances at compile time.


def cmp_to_key(mycmp):
    """Convert a two-argument comparator into a sorting key function."""
    # Pystachy port: the closure is the key factory; its objects retain the
    # fallback's obj attribute and five comparison methods.
    def key(obj):
        return _CmpKey(obj, mycmp)

    return key


def reduce(function, sequence, /, *initial):
    """Apply a function cumulatively to the items, from left to right.

    The initial value, when supplied, precedes the sequence's first item.
    Without it an empty sequence raises TypeError. The accumulator and callback
    have the types inferred for this call, as with the other subset templates.
    """
    # Pystachy port: CPython 3.13.16's Python fallback uses an object() default
    # sentinel and iter()/next(), none of which have subset types. A zero-or-one
    # positional tuple distinguishes an omitted initial from an explicit None.
    # One for loop remembers whether its first item supplies the accumulator,
    # preserving single-pass streams, iteration order and list mutation.
    if len(initial) > 1:
        raise TypeError("reduce expected at most 3 arguments, got " + str(2 + len(initial)))
    if len(initial) == 0:
        have_value = False
        for element in sequence:
            if not have_value:
                value = element
                have_value = True
            else:
                value = function(value, element)
        if not have_value:
            raise TypeError("reduce() of empty iterable with no initial value")
    else:
        value = initial[0]
        for element in sequence:
            value = function(value, element)
    return value


class CacheInfo(NamedTuple):
    """CPython's _CacheInfo, namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])"""

    hits: int
    misses: int
    maxsize: int | None
    currsize: int


_CacheInfo = CacheInfo


class _lru_cache_wrapper(Generic[*_Ts, _R]):
    """A function wrapped with a cache: maxsize < 0 caches every result (maxsize=None), 0 none, and
    maxsize > 0 the results of the most recently used calls."""

    def __init__(self, user_function: Callable[[*_Ts], _R], maxsize: int, typed: bool) -> None:
        self.__wrapped__ = user_function
        self.__name__: str = user_function.__name__
        self.__qualname__: str = user_function.__qualname__
        self._maxsize = maxsize
        self._typed = typed  # (a parameter has one type, so typed=True keeps no calls apart that False merges)
        self._hits = 0
        self._misses = 0
        # maxsize < 0: the results, by key
        self._cache: dict[tuple[*_Ts], _R] = {}
        self._form_cache: dict[tuple[int, tuple[*_Ts]], _R] = {}
        # maxsize > 0: the links of a circular doubly linked list, from the root (0) to the least
        # recently used link and on to the most recently used one, as CPython's lru_list_elem: link i
        # holds _keys[i - 1] and _results[i - 1], _links finds it by key
        self._links: dict[tuple[*_Ts], int] = {}
        self._form_links: dict[tuple[int, tuple[*_Ts]], int] = {}
        self._keys: list[tuple[*_Ts]] = []
        self._forms: list[int] = []
        self._results: list[_R] = []
        self._prev: list[int] = [0]
        self._next: list[int] = [0]

    def _extract(self, link: int) -> None:
        # lru_cache_extract_link
        prev = self._prev[link]
        nxt = self._next[link]
        self._next[prev] = nxt
        self._prev[nxt] = prev

    def _append(self, link: int) -> None:
        # lru_cache_append_link: the most recently used
        last = self._prev[0]
        self._next[last] = link
        self._prev[0] = link
        self._prev[link] = last
        self._next[link] = 0

    def __call__(self, *args: *_Ts) -> _R:
        return self._call(0, *args)

    def _call(self, shape: int, *key: *_Ts) -> _R:
        # The compiler binds a cached call against __wrapped__'s signature and passes its
        # call shape followed by the bound values. Different spellings share this one LRU
        # but keep separate entries. Full positional calls keep the original key layout;
        # other forms use a second lookup map into the SAME LRU, capacity and statistics.
        if self._maxsize == 0:
            # uncached_lru_cache_wrapper
            self._misses += 1
            return self.__wrapped__(*key)
        if self._maxsize < 0:
            # infinite_lru_cache_wrapper
            if shape == 0:
                if key in self._cache:
                    self._hits += 1
                    return self._cache[key]
            else:
                if (shape, key) in self._form_cache:
                    self._hits += 1
                    return self._form_cache[(shape, key)]
            self._misses += 1
            result = self.__wrapped__(*key)
            if shape == 0:
                self._cache[key] = result
            else:
                self._form_cache[(shape, key)] = result
            return result
        # bounded_lru_cache_wrapper
        if shape == 0:
            link = self._links.get(key, 0)
        else:
            link = self._form_links.get((shape, key), 0)
        if link != 0:
            if self._prev[0] != link:  # (moving the most recently used link changes nothing)
                self._extract(link)
                self._append(link)
            self._hits += 1
            return self._results[link - 1]
        self._misses += 1
        result = self.__wrapped__(*key)
        if (key in self._links) if shape == 0 else ((shape, key) in self._form_links):
            # the call added this key (it called the function again): only the result is returned
            return result
        if len(self._links) + len(self._form_links) < self._maxsize or self._next[0] == 0:
            # not full: a new link
            self._keys.append(key)
            self._forms.append(shape)
            self._results.append(result)
            self._prev.append(0)
            self._next.append(0)
            link = len(self._keys)
            if shape == 0:
                self._links[key] = link
            else:
                self._form_links[(shape, key)] = link
            self._append(link)
            return result
        # full: the least recently used link takes the new key and result
        link = self._next[0]
        self._extract(link)
        if self._forms[link - 1] == 0:
            del self._links[self._keys[link - 1]]
        else:
            del self._form_links[(self._forms[link - 1], self._keys[link - 1])]
        self._keys[link - 1] = key
        self._forms[link - 1] = shape
        self._results[link - 1] = result
        if shape == 0:
            self._links[key] = link
        else:
            self._form_links[(shape, key)] = link
        self._append(link)
        return result

    def cache_info(self) -> CacheInfo:
        """Report cache statistics"""
        if self._maxsize < 0:
            return CacheInfo(self._hits, self._misses, None, len(self._cache) + len(self._form_cache))
        return CacheInfo(self._hits, self._misses, self._maxsize, len(self._links) + len(self._form_links))

    def cache_clear(self) -> None:
        """Clear the cache and cache statistics"""
        self._hits = 0
        self._misses = 0
        self._cache.clear()
        self._form_cache.clear()
        self._links.clear()
        self._form_links.clear()
        self._keys.clear()
        self._forms.clear()
        self._results.clear()
        self._prev = [0]
        self._next = [0]


def _make_wrapper(user_function, maxsize: int, typed: bool):
    # CPython supplies its C wrapper. Pystachy folds this optional import away and
    # uses the subset implementation, whose call-shape binding the compiler provides.
    try:
        import _functools
        wrapper = _functools._lru_cache_wrapper(user_function, None if maxsize < 0 else maxsize, typed, CacheInfo)
        wrapper.__wrapped__ = user_function
        wrapper.__name__ = user_function.__name__
        wrapper.__qualname__ = user_function.__qualname__
        return wrapper
    except ImportError:
        return _lru_cache_wrapper(user_function, maxsize, typed)


def lru_cache(maxsize=128, typed=False):
    """Least-recently-used cache decorator.

    If *maxsize* is set to None, the LRU features are disabled and the cache
    can grow without bound.

    View the cache statistics named tuple (hits, misses, maxsize, currsize)
    with f.cache_info().  Clear the cache and statistics with
    f.cache_clear().  Access the underlying function with f.__wrapped__.
    """
    if isinstance(maxsize, int):
        # Negative maxsize is treated as 0 (and a bool as the int it is, as CPython's C wrapper takes it)
        size = int(maxsize)
        if size < 0:
            size = 0

        def decorating_function(user_function):
            return _make_wrapper(user_function, size, typed)

        return decorating_function
    if maxsize is None:

        def unbounded_function(user_function):
            return _make_wrapper(user_function, -1, typed)

        return unbounded_function
    # The user_function was passed in directly via the maxsize argument (@lru_cache)
    return _make_wrapper(maxsize, 128, typed)


def cache(user_function, /):
    'Simple lightweight unbounded cache.  Sometimes called "memoize".'
    return lru_cache(maxsize=None)(user_function)
