# pystachy: dynamic-any
# isinstance() narrows an Any parameter or local to the type its box holds; a function may
# return values of several types, and a variable change type in a loop.
from typing import Any


def describe(v: Any) -> str:
    if isinstance(v, bool):
        return "bool " + str(not v)
    if isinstance(v, int):
        return "int " + str(v * 2)
    elif isinstance(v, float):
        return "float " + str(v / 2)
    elif isinstance(v, str):
        return "str " + v.upper() + str(len(v))
    elif isinstance(v, list):
        return "list of " + str(len(v)) + " first " + repr(v[0] if len(v) > 0 else None)
    elif isinstance(v, dict):
        return "dict keys " + repr(sorted([str(k) for k in v]))
    elif isinstance(v, tuple):
        return "tuple " + repr(v)
    elif v is None:
        return "none"
    return "other"


def parse(text: str) -> Any:
    if text == "":
        return None
    if text.isdigit():
        return int(text)
    if text.startswith("[") and text.endswith("]"):
        return [parse(p) for p in text[1:-1].split(",")]
    try:
        return float(text)
    except ValueError:
        return text


def total(xs: list[Any]) -> Any:
    acc: Any = 0
    for x in xs:
        if isinstance(acc, str):
            acc = acc + str(x)
        elif isinstance(x, int) or isinstance(x, float):
            acc = acc + x
        elif isinstance(x, str):
            acc = str(acc) + x
            continue
    return acc


for v in [1, True, 2.5, "hi", [3, "x"], {"b": 1, "a": 2}, (1, "t"), None]:
    print(describe(v))
for t in ["12", "", "1.5", "word", "[1,2,x]"]:
    r = parse(t)
    print(repr(r), describe(r))
print(total([1, 2.5, 3]))
print(total([1, 2, "s", 4]))
y: Any = 0
for i in range(5):
    if i % 2 == 0:
        y = i
    else:
        y = str(i) * i
    print(y, type(y).__name__)
