# pystachy: dynamic-any
# isinstance(x, range) of an Any value that holds a range object is true (#1581): a range object
# is boxed as an object of the subset's range class, which the test names. The local is that
# object after the test
from typing import Any


def kinds(tag: str, v: Any) -> None:
    print(tag, isinstance(v, range), isinstance(v, (range, list)), isinstance(v, (int, str)), isinstance(v, range | None))


def spanned(v: Any) -> str:
    if isinstance(v, range):
        return f"range of {len(v)} from {v.start} to {v.stop} by {v.step}: {list(v)}"
    return "no range"


values: list[Any] = [range(3), range(1, 10, 4), range(0), [0, 1, 2], (0, 1, 2), 3, "range", None]
tags = ["range", "stepped", "empty", "list", "tuple", "int", "str", "none"]
for i in range(len(values)):
    kinds(tags[i], values[i])
    print(spanned(values[i]))
print([isinstance(v, range) for v in values])
