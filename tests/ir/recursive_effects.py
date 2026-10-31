# The effects of comparing and printing recursive alias values (recursive_effects.fx). The
# runtime's descriptor walks count only a recursive alias's edges, and raise RecursionError past
# 512 of them, so an operation that walks a value by its descriptor (RUNTIME's R?) may raise only
# where the descriptor holds such an edge: ==, in, count() and repr() of V raise (R), the same
# operations on lists of lists do not, and neither does storing V values in a dict with str keys.
# Source-function summaries also include R I for their recursion entry/exit guards.
type V = int | list[V]


def rec_eq(a: V, b: V) -> bool:
    return a == b


def plain_eq(a: list[list[int]], b: list[list[int]]) -> bool:
    return a == b


def rec_in(xs: list[V], x: V) -> bool:
    return x in xs


def plain_in(xs: list[list[int]], x: list[int]) -> bool:
    return x in xs


def rec_count(xs: list[V], x: V) -> int:
    return xs.count(x)


def plain_count(xs: list[list[int]], x: list[int]) -> int:
    return xs.count(x)


def rec_repr(v: V) -> str:
    return repr(v)


def plain_repr(v: list[list[int]]) -> str:
    return repr(v)


def rec_store(d: dict[str, V], k: str, v: V) -> None:
    d[k] = v


def rec_has(d: dict[str, V], k: str) -> bool:
    return k in d


nested: V = [1, [2]]
print(rec_eq(nested, nested), plain_eq([[1]], [[1]]), rec_in([nested], nested), plain_in([[1]], [1]))
print(rec_count([nested], nested), plain_count([[1]], [1]), rec_repr(nested), plain_repr([[1]]))
values: dict[str, V] = {}
rec_store(values, "a", nested)
print(rec_has(values, "a"))
