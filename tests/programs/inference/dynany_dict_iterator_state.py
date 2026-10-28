# pystachy: dynamic-any
# A keys-changed error exhausts dict iterators; a size-change error stays live.
from typing import Any


def advance(it: Any) -> None:
    try:
        print(next(it, "done"))
    except RuntimeError as error:
        print(error)


d: Any = {"a": 1, "b": 2}
it = iter(d)
print("dynamic keys", next(it))
del d["a"]
d["c"] = 3
print(next(it))
advance(it)
advance(it)
d.clear()
advance(it)

# A boxed typed iterator still walks the original keys, values or items.
for mode in ["keys", "values", "items"]:
    typed: dict[str, Any] = {"a": 1, "b": 2}
    cursor: Any = None
    if mode == "keys":
        cursor = iter(typed.keys())
    elif mode == "values":
        cursor = iter(typed.values())
    else:
        cursor = iter(typed.items())
    print(mode, next(cursor))
    del typed["a"]
    typed["c"] = 3
    print(next(cursor))
    advance(cursor)
    advance(cursor)
    typed.clear()
    advance(cursor)

# Reverse iteration also checks the remaining count when a same-size rebuild
# puts extra entries below its old position (CPython 3.13.16).
reverse: Any = {18: 0, 27: 1, 12: 2, 20: 3, 29: 4}
del reverse[27]
del reverse[20]
back = reversed(reverse)
print("reverse keys", next(back), next(back))
reverse.clear()
reverse[21] = 0
reverse[22] = 1
reverse[23] = 2
advance(back)
advance(back)
advance(back)
reverse.clear()
advance(back)

# Size changes remain errors even when the original size is restored, in both
# directions; the keys-changed exhaustion fix must not swallow those errors.
for backwards in [False, True]:
    changed: Any = {"a": 1, "b": 2}
    remaining = reversed(changed) if backwards else iter(changed)
    print("size change", backwards, next(remaining))
    changed["c"] = 3
    advance(remaining)
    del changed["c"]
    advance(remaining)
    changed.clear()
    advance(remaining)
