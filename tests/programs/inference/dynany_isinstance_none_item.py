# pystachy: dynamic-any
# None in the tuple that isinstance() takes is no type: CPython tests the items in order and
# raises TypeError where it reaches the None, so a value of a type before it is an instance and
# any other value raises (#1581). int | None names NoneType, and so does type(None)
from typing import Any


def tested(tag: str, v: Any) -> None:
    out: list[str] = []
    try:
        out.append(str(isinstance(v, (int, None))))
    except TypeError as e:
        out.append(f"TypeError: {e}")
    try:
        out.append(str(isinstance(v, (None,))))
    except TypeError:
        out.append("TypeError")
    try:
        out.append(str(isinstance(v, (int, (str, None), float))))
    except TypeError:
        out.append("TypeError")
    try:
        out.append(str(isinstance(v, (object, None))))
    except TypeError:
        out.append("TypeError")
    out.append(str(isinstance(v, int | None)))
    out.append(str(isinstance(v, (int, type(None)))))
    print(tag, out)


def bumped(v: Any) -> Any:
    # (where the test is true, v is an int: the None item raised for anything else)
    try:
        if isinstance(v, (int, None)):
            return v + 1
        return "unreached"
    except TypeError:
        return "TypeError"


values: list[Any] = [5, True, "s", 2.5, None, [1]]
tags = ["int", "bool", "str", "float", "none", "list"]
for i in range(len(values)):
    tested(tags[i], values[i])
    print(bumped(values[i]))
