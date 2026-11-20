# pystachy: dynamic-any
# deques of different item types held as Any values: CPython compares their items, so a deque of
# ints equals one of the floats or of the Any values that equal them, and none of strs, in
# either operand order; searches of Any containers compare them the same way. An ordering of a
# deque of ints and one of strs raises TypeError, as before
from collections import deque
from typing import Any


def cmp(a: Any, b: Any) -> str:
    return f"{a == b} {b == a} {a != b} {b != a}"


def less(a: Any, b: Any) -> str:
    try:
        return str(a < b)
    except TypeError:
        return "TypeError"


one: Any = 1
ints: Any = deque([1, 2])
strs: Any = deque(["a", "b"])
floats: Any = deque([1.0, 2.0])
boxes: Any = deque([one, 2])
texts: Any = deque([one, "b"])
print(cmp(ints, strs), cmp(ints, floats), cmp(ints, boxes), cmp(ints, texts))
print(cmp(strs, floats), cmp(strs, texts), cmp(floats, boxes), cmp(boxes, texts))
print(cmp(deque[int](), deque[str]()), cmp(deque[int](), strs), cmp(ints, deque([1.0])))
strs.appendleft("z")
texts.popleft()
texts.appendleft("a")
texts.appendleft("z")
print(cmp(strs, texts), cmp(ints, strs))
held: list[Any] = [strs, 5, floats]
print(ints in held, held.index(ints), held.count(ints), boxes in held, deque(["z"]) in held)
print(less(ints, strs), less(strs, ints))
