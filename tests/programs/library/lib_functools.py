# lib/functools: cache() and lru_cache(), against CPython's C _lru_cache_wrapper. Each decorated
# function prints when it runs, so the output shows which calls the cache answered, and
# cache_info() after each step shows CPython's statistics: hits, misses, maxsize and currsize.
from functools import cache, lru_cache


@lru_cache(maxsize=3)
def square(n: int) -> int:
    print("  square", n)
    return n * n


print("bounded, maxsize=3")
for x in [1, 2, 1, 3, 4, 1, 2, 5, 3]:
    print(x, square(x), square.cache_info())
# the least recently used goes first: 1 2 3 here, then 4 is the oldest
print(square(4), square.cache_info())
square.cache_clear()
print("cleared", square.cache_info())
print(square(1), square.cache_info())


@lru_cache(maxsize=1)
def one(s: str) -> str:
    print("  one", s)
    return s + s


print("maxsize=1:", one("a"), one("a"), one("b"), one("a"), one.cache_info())


@cache
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


print("cache:", fib(90), fib.cache_info())
fib.cache_clear()
print(fib(10), fib.cache_info())


@lru_cache(maxsize=None)
def unbounded(n: int) -> int:
    print("  unbounded", n)
    return -n


print("maxsize=None:", unbounded(1), unbounded(2), unbounded(1), unbounded.cache_info())


@lru_cache(maxsize=0)
def nocache(n: int) -> int:
    print("  nocache", n)
    return n + 1


@lru_cache(maxsize=-5)
def negative(n: int) -> int:
    print("  negative", n)
    return n + 2


print("maxsize=0:", nocache(1), nocache(1), nocache.cache_info())
print("maxsize=-5:", negative(1), negative(1), negative.cache_info())


@lru_cache
def bare(n: int) -> int:
    print("  bare", n)
    return n * 10


print("@lru_cache:", bare(1), bare(1), bare.cache_info())


def triple(n: int) -> int:
    print("  triple", n)
    return 3 * n


tri = lru_cache(maxsize=2)(triple)
print("lru_cache(2)(f):", tri(1), tri(2), tri(1), tri(3), tri(2), tri.cache_info())
print("__wrapped__:", tri.__wrapped__(1), tri.cache_info())
print("names:", tri.__name__, tri.__qualname__, square.__name__, fib.__qualname__)
cached_triple = cache(triple)
print("cache(f):", cached_triple(4), cached_triple(4), cached_triple.cache_info())


# falsy results are cached too, and a result is the object the function returned
@lru_cache(maxsize=8)
def falsy(n: int) -> str:
    print("  falsy", n)
    return ""


@lru_cache(maxsize=8)
def zero(s: str) -> int:
    print("  zero", s)
    return 0


@lru_cache(maxsize=8)
def items(n: int) -> list[int]:
    print("  items", n)
    return list(range(n))


print("falsy:", repr(falsy(1)), repr(falsy(1)), zero("x"), zero("x"), falsy.cache_info(), zero.cache_info())
a = items(3)
a.append(99)
b = items(3)
print("same object:", a is b, b, items.cache_info())


# an exception is not cached: the next call runs the function again
@lru_cache(maxsize=4)
def checked(n: int) -> int:
    print("  checked", n)
    if n < 0:
        raise ValueError(f"negative: {n}")
    return n


for x in [1, -1, -1, 1]:
    try:
        print(checked(x))
    except ValueError as e:
        print("ValueError", e)
print(checked.cache_info())


# parameters of other types make a tuple key, as CPython's key is the tuple of the arguments
@lru_cache(maxsize=4)
def join(a: str, n: int, flag: bool) -> str:
    print("  join", a, n, flag)
    return a * n if flag else a


print("tuple keys:", join("ab", 2, True), join("ab", 2, True), join("ab", 2, False), join("ab", 3, True))
print(join.cache_info())


@lru_cache(maxsize=4)
def pair(p: tuple[int, str], q: str | None) -> str:
    print("  pair", p, q)
    return p[1] * p[0] + (q if q is not None else "-")


print("tuple and str | None:", pair((2, "x"), None), pair((2, "x"), None), pair((2, "x"), "y"), pair.cache_info())


@lru_cache(maxsize=2)
def flag(b: bool) -> str:
    print("  flag", b)
    return "yes" if b else "no"


print("bool:", flag(True), flag(False), flag(True), flag.cache_info())


@cache
def config() -> dict[str, int]:
    print("  config")
    return {"retries": 3}


c1 = config()
c1["retries"] += 1
print("no parameters:", config(), config.cache_info())


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


@lru_cache(maxsize=2)
def point(n: int) -> Point:
    print("  point", n)
    return Point(n, -n)


p1 = point(1)
print("objects:", p1.x, point(1) is p1, point(2).y, point(3).y, point(1) is p1, point.cache_info())


@lru_cache(maxsize=2)
def maybe(n: int) -> int | None:
    print("  maybe", n)
    return n if n > 0 else None


print("int | None:", maybe(1), maybe(0), maybe(0), maybe(1), maybe.cache_info())


# a wrapper is made each time the decorator runs: a def inside a function gets a cache per call
def make(k: int) -> None:
    @lru_cache(maxsize=2)
    def times(n: int) -> int:
        print("  times", k, n)
        return k * n

    print(times(2), times(2), times(3), times.cache_info())


print("closures:")
make(10)
make(20)


# a call that adds its own key while it runs (it calls itself with the same argument): the
# outer call returns what it computed and leaves the cache as the inner call left it
depth = [0]


@lru_cache(maxsize=4)
def reentrant(n: int) -> list[int]:
    depth[0] += 1
    if depth[0] == 1:
        print("  inner", reentrant(n))
    return [n, depth[0]]


outer = reentrant(7)
again = reentrant(7)
print("reentrant:", outer, again, outer is again, reentrant.cache_info())


# the function clears its own cache while it runs: the result goes into the emptied cache
@lru_cache(maxsize=2)
def clearing(n: int) -> int:
    print("  clearing", n)
    if n == 3:
        clearing.cache_clear()
    return n


print("clear inside:", clearing(1), clearing(2), clearing(3), clearing.cache_info(), clearing(1), clearing.cache_info())


# a full cache, every call new: each miss evicts the least recently used result
@lru_cache(maxsize=100)
def text(n: int) -> str:
    return str(n) * 1000


total = 0
for i in range(5000):
    total += len(text(i % 150))
print("churn:", total, text.cache_info())
for i in [149, 50, 49]:
    text(i)
print(text.cache_info())


# mutual recursion through two caches
@lru_cache(maxsize=None)
def even(n: int) -> bool:
    return True if n == 0 else odd(n - 1)


@lru_cache(maxsize=None)
def odd(n: int) -> bool:
    return False if n == 0 else even(n - 1)


print("mutual:", even(50), odd(51), even.cache_info(), odd.cache_info())
