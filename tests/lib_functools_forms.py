# lib/functools: the forms of a call through lru_cache(). CPython's key of a call is its positional
# arguments, then a marker and each keyword argument's name and value in the call's order, so
# f(3), f(3, 2), f(3, k=2), f(x=3, k=2) and f(k=2, x=3) are five entries even where the function
# sees the same arguments; the same form with the same values is one entry.
from functools import cache, lru_cache


@lru_cache(maxsize=8)
def scale(x: int, k: int = 2, *, label: str = "") -> str:
    print("  scale", x, k, repr(label))
    return label + str(x * k)


print(scale(3), scale(3, 2), scale(3, k=2), scale(x=3, k=2), scale(k=2, x=3))
print(scale.cache_info())
print(scale(3), scale(3, 2), scale(3, k=2), scale(x=3, k=2), scale(k=2, x=3))
print(scale.cache_info())
print(scale(3, label="a"), scale(3, 2, label="a"), scale(3, label="a"), scale(4, label="a"))
print(scale.cache_info())
# the forms share one cache: its capacity, its order of use and its statistics
print(scale(5), scale(5, k=1), scale(6), scale(3), scale.cache_info())
print(scale(k=2, x=3), scale.cache_info())


# positional-only and keyword-only parameters, and defaults of every type a key holds
@cache
def fmt(text: str, /, width: int = 8, *, fill: str = " ", upper: bool = False, tag: str | None = None) -> str:
    print("  fmt", repr(text), width, repr(fill), upper, tag)
    s = text.upper() if upper else text
    return (tag + ":" if tag is not None else "") + s.rjust(width, fill)


print(fmt("ab"), fmt("ab", 4), fmt("ab", width=4), fmt("ab", fill="."), fmt("ab", upper=True, fill="."))
print(fmt("ab", fill=".", upper=True), fmt("ab", tag="t"), fmt("ab", tag=None), fmt("ab", 4, tag="t"))
print(fmt.cache_info())
print(fmt("ab"), fmt("ab", 4), fmt("ab", width=4), fmt("ab", fill=".", upper=True), fmt("ab", tag=None))
print(fmt.cache_info())


@lru_cache(maxsize=2)
def pair(p: tuple[int, int] = (1, 2), q: int = 0) -> int:
    print("  pair", p, q)
    return p[0] * p[1] + q


print(pair(), pair((1, 2)), pair(q=0), pair(), pair.cache_info())


# a function wrapped twice keeps two caches; a form seen by one is no form of the other's yet
def area(w: int, h: int = 1) -> int:
    print("  area", w, h)
    return w * h


a1 = lru_cache(maxsize=4)(area)
a2 = cache(area)
print(a1(2, h=3), a2(2, h=3), a1(2, h=3), a2(2), a2(w=2), a1.cache_info(), a2.cache_info())


# recursion through keyword arguments
@cache
def walk(n: int, acc: int = 0) -> int:
    return acc if n == 0 else walk(n - 1, acc=acc + n)


print(walk(30), walk.cache_info())
