# Cache keys preserve how arguments were supplied, while defaults bind as for a def.
from functools import cache, lru_cache
from typing import Callable

calls = [0]


@lru_cache(maxsize=4)
def pair(a: int = 1, b: int = 2) -> int:
    calls[0] += 1
    return calls[0] * 100 + a * 10 + b


print("forms", pair(1), pair(1, 2), pair(1, b=2), pair(a=1, b=2), pair.cache_info())
print("hits", pair(1), pair(1, 2), pair(1, b=2), pair(a=1, b=2), pair.cache_info())
print("order", pair(b=2, a=1), pair(b=2, a=1), pair.cache_info())
print("evicted", pair(1), pair.cache_info())
pair.cache_clear()
print("empty", pair(), pair(), pair.cache_info())

# Aliases, explicit __call__, and a bound __call__ use the same positional shape.
alias = pair
bound = pair.__call__


def callback(fn: Callable[[int, int], int]) -> int:
    return fn(1, 2)


print("aliases", pair(1, 2), alias(1, 2), pair.__call__(1, 2), bound(1, 2), callback(bound), pair.cache_info())
print("bound keyword", bound(b=2, a=1), pair(b=2, a=1), pair.cache_info())
print("wrapped", pair.__wrapped__(b=2, a=1), pair.cache_info())

# Calls evaluate in source order, then bind in parameter order; defaults evaluate once.
effects: list[str] = []


def mark(label: str, value: int) -> int:
    effects.append(label)
    return value


@cache
def ordered(a: int, b: int = mark("default", 2)) -> int:
    effects.append("body")
    return a * 10 + b


print("eval", ordered(b=mark("b", 2), a=mark("a", 1)), effects)
print("eval hit", ordered(b=mark("b2", 2), a=mark("a2", 1)), effects)
print("default", ordered(mark("pos", 1)), ordered(1), effects, ordered.cache_info())
print("expansion", ordered(*(1,), **{"b": 2}), ordered(1, b=2), ordered.cache_info())
print("kw expansion", ordered(**{"b": 2, "a": 1}), ordered(**{"a": 1, "b": 2}), ordered.cache_info())


def local(k: int) -> None:
    @lru_cache(maxsize=3)
    def add(a: int = k, b: str = "!") -> str:
        return str(a) + b

    print("closure", add(), add(), add(b="!"), add(a=k), add(k, "!"), add.cache_info())


local(3)
local(4)


@cache
def optional(s: str | None = None) -> str:
    return "none" if s is None else s


print("optional", optional(), optional(None), optional(s=None), optional(), optional.cache_info())


@lru_cache(maxsize=0)
def disabled(a: int = 3) -> int:
    return a


print("disabled", disabled(), disabled(a=3), disabled(3), disabled.cache_info())


@cache
def positional(a: int = 2, /) -> int:
    return a


print("positional", positional(), positional(2), positional(), positional.cache_info())


@cache
def keyword_default(a: int, *, b: int = 5) -> int:
    return a + b


print("kw-only omitted", keyword_default(1), keyword_default(a=1), keyword_default.cache_info())

# Reentrancy across different shapes still uses one shared cache and one capacity.
depth = [0]


@lru_cache(maxsize=2)
def recursive(a: int = 7) -> int:
    depth[0] += 1
    if depth[0] == 1:
        print("inner", recursive(a=a))
    return depth[0]


print("recursive", recursive(), recursive(a=7), recursive(), recursive.cache_info())


@lru_cache(maxsize=2)
def clear_inside(a: int = 2) -> int:
    if a == 2:
        clear_inside.cache_clear()
    return a


print("clear", clear_inside(1), clear_inside(), clear_inside(a=2), clear_inside.cache_info())


@cache
def failing(a: int = -1) -> int:
    if a < 0:
        raise ValueError("negative")
    return a


for i in range(2):
    try:
        failing()
    except ValueError as e:
        print(e)
print("raises", failing.cache_info())


# Nine arguments were already supported; adding a call shape must not exceed that limit.
@lru_cache(maxsize=2)
def nine(a: int, b: int, c: int, d: int, e: int, f: int, g: int, h: int, i: int = 9) -> int:
    return a + b + c + d + e + f + g + h + i


print("nine", nine(1, 2, 3, 4, 5, 6, 7, 8, 9), nine(1, 2, 3, 4, 5, 6, 7, 8), nine.cache_info())
print("nine hit", nine(1, 2, 3, 4, 5, 6, 7, 8, 9), nine(1, 2, 3, 4, 5, 6, 7, 8), nine.cache_info())

print("nine keywords", nine(a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=8, i=9), nine.cache_info())
print("nine keywords hit", nine(a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=8, i=9), nine.cache_info())
