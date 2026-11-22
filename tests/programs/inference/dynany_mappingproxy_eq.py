# pystachy: dynamic-any
# A mapping proxy held as an Any value compares as CPython's does: with a value that is no
# mapping it is unequal, in either operand order, and with a dict, another proxy or one of
# collections' mappings it compares its dict's items, whatever their static types. An ordering
# raises TypeError, and searches of Any lists pass over other values.
from collections import Counter, OrderedDict, defaultdict
from types import MappingProxyType
from typing import Any


def eq(a: Any, b: Any) -> str:
    return f"{a == b}{b == a}{a != b}{b != a}"


def less(a: Any, b: Any) -> str:
    try:
        return str(a < b)
    except TypeError:
        return "TypeError"


source = {"k": 1}
view: Any = MappingProxyType(source)
others: list[Any] = [5, "k", [1], None, 2.5, ("k", 1), True]
print(" ".join(eq(view, o) for o in others))
print(view in others, others.count(view), less(view, 5), less(5, view))

same: Any = {"k": 1}
more: Any = {"k": 1, "j": 2}
empty: Any = {}
print(eq(view, same), eq(view, more), eq(view, empty))
mixed: list[Any] = [5, more, same]
print(view in mixed, mixed.index(view), mixed.count(view), less(view, same))

again: Any = MappingProxyType({"k": 1})
anys: dict[Any, Any] = {"k": 1}
loose: Any = MappingProxyType(anys)
ints: Any = MappingProxyType({1: "k"})
print(eq(view, view), eq(view, again), eq(view, loose), eq(view, ints), eq(loose, ints))

ordered: Any = OrderedDict([("k", 1)])
default: Any = defaultdict(int, {"k": 1})
counts: Any = Counter("k")
zero: Any = Counter({"k": 1, "j": 0})
print(eq(view, ordered), eq(view, default), eq(view, counts), eq(view, zero))

source["j"] = 2
print(eq(view, same), eq(view, more), eq(view, ordered))
