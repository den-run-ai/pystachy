"""functools for Pystachy: cache() and lru_cache(), written in the subset.

Pystachy's own stand-in for CPython 3.13's Lib/functools.py, whose lru_cache() wraps the C type
_functools._lru_cache_wrapper (Modules/_functoolsmodule.c). The wrapper below follows that C code:
the same three behaviours by maxsize (no caching, unbounded, least recently used), the same
statistics, and the same order of lookups, calls and updates, so a function that calls itself or
clears its own cache sees what it sees under CPython.

A Pystachy dict holds keys of one type and values of another, so each decorated function gets a
cache of its own types: _lru_cache_wrapper is a class template (its __init__ takes the function
without an annotation), and the compiler binds _Key and _Result in the specialization each function
makes, from that function's signature: _Result is its return type, and _Key the type of the key
__pys_cache_key() makes of a call, which keeps each form of a call apart as CPython's key does
(f(3), f(3, 2) and f(3, k=2) are three entries) (lib/README.md, *functools*).
"""

from typing import NamedTuple, TypeVar

__all__ = ["cache", "lru_cache"]

_Key = TypeVar("_Key")  # the key of a call (bound by the compiler, see above)
_Result = TypeVar("_Result")  # what the decorated function returns (bound by the compiler)


class CacheInfo(NamedTuple):
    """CPython's _CacheInfo, namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])"""

    hits: int
    misses: int
    maxsize: int | None
    currsize: int


_CacheInfo = CacheInfo


class _lru_cache_wrapper:
    """A function wrapped with a cache: maxsize < 0 caches every result (maxsize=None), 0 none, and
    maxsize > 0 the results of the most recently used calls."""

    def __init__(self, user_function, maxsize: int, typed: bool) -> None:
        self.__wrapped__ = user_function
        self.__name__: str = user_function.__name__
        self.__qualname__: str = user_function.__qualname__
        self._maxsize = maxsize
        self._typed = typed  # (a parameter has one type, so typed=True keeps no calls apart that False merges)
        self._hits = 0
        self._misses = 0
        # maxsize < 0: the results, by key
        self._cache: dict[_Key, _Result] = {}
        # maxsize > 0: the links of a circular doubly linked list, from the root (0) to the least
        # recently used link and on to the most recently used one, as CPython's lru_list_elem: link i
        # holds _keys[i - 1] and _results[i - 1], _links finds it by key
        self._links: dict[_Key, int] = {}
        self._keys: list[_Key] = []
        self._results: list[_Result] = []
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

    def __call__(self, *args, **kwds) -> _Result:
        if self._maxsize == 0:
            # uncached_lru_cache_wrapper
            self._misses += 1
            return self.__wrapped__(*args, **kwds)
        key = __pys_cache_key(self, *args, **kwds)
        if self._maxsize < 0:
            # infinite_lru_cache_wrapper
            if key in self._cache:
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            result = self.__wrapped__(*args, **kwds)
            self._cache[key] = result
            return result
        # bounded_lru_cache_wrapper
        link = self._links.get(key, 0)
        if link != 0:
            if self._prev[0] != link:  # (moving the most recently used link changes nothing)
                self._extract(link)
                self._append(link)
            self._hits += 1
            return self._results[link - 1]
        self._misses += 1
        result = self.__wrapped__(*args, **kwds)
        if key in self._links:
            # the call added this key (it called the function again): only the result is returned
            return result
        if len(self._links) < self._maxsize or self._next[0] == 0:
            # not full: a new link
            self._keys.append(key)
            self._results.append(result)
            self._prev.append(0)
            self._next.append(0)
            link = len(self._keys)
            self._links[key] = link
            self._append(link)
            return result
        # full: the least recently used link takes the new key and result
        link = self._next[0]
        self._extract(link)
        del self._links[self._keys[link - 1]]
        self._keys[link - 1] = key
        self._results[link - 1] = result
        self._links[key] = link
        self._append(link)
        return result

    def cache_info(self) -> CacheInfo:
        """Report cache statistics"""
        if self._maxsize < 0:
            return CacheInfo(self._hits, self._misses, None, len(self._cache))
        return CacheInfo(self._hits, self._misses, self._maxsize, len(self._links))

    def cache_clear(self) -> None:
        """Clear the cache and cache statistics"""
        self._hits = 0
        self._misses = 0
        self._cache.clear()
        self._links.clear()
        self._keys.clear()
        self._results.clear()
        self._prev = [0]
        self._next = [0]


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
            return _lru_cache_wrapper(user_function, size, typed)

        return decorating_function
    if maxsize is None:

        def unbounded_function(user_function):
            return _lru_cache_wrapper(user_function, -1, typed)

        return unbounded_function
    # The user_function was passed in directly via the maxsize argument (@lru_cache)
    return _lru_cache_wrapper(maxsize, 128, typed)


def cache(user_function, /):
    'Simple lightweight unbounded cache.  Sometimes called "memoize".'
    return lru_cache(maxsize=None)(user_function)
