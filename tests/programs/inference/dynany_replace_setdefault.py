# pystachy: dynamic-any
# A str's replace() through Any takes its count, and a dict's setdefault() a key alone, whose
# default is None, as CPython's do; their arguments are evaluated before an arity error.
from typing import Any


def arg(value: Any) -> Any:
    print("argument", repr(value))
    return value


s: Any = "a-b-c-d"
print(s.replace("-", "+", 2), s.replace("-", "", 0), s.replace("-", "=", -1), s.replace("", "|", 2))
count: Any = True
print(s.replace("-", "", count))
d: Any = {"a": 1}
print(d.setdefault("b"), d, d.setdefault("a"), d.setdefault(arg("c"), 3), d)
for bad in [lambda: s.replace(arg("-")), lambda: s.replace("-", "+", 1, arg(2)), lambda: d.setdefault(), lambda: d.setdefault(arg("x"), 1, 2)]:
    try:
        print(bad())
    except TypeError as error:
        print("TypeError", error)
try:
    print(s.replace("-", "+", "2"))
except TypeError as error:
    print("TypeError", error)
