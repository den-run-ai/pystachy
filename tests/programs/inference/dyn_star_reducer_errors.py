# pystachy: dynamic-any
# Runtime unpacking preserves first errors, merge order and signature checks.
from typing import Any

EVENTS: list[str] = []


def target(a: int, /, b: int = 2, *, flag: bool = True) -> int:
    EVENTS.append("called")
    return a + b if flag else -a - b


def note(label: str, value: Any) -> Any:
    EVENTS.append(label)
    return value


function: Any = target
for which in range(8):
    EVENTS.clear()
    try:
        if which == 0:
            function(*note("not iterable", 4), flag=note("keyword", True))
        elif which == 1:
            function(*note("args", [1, 2, 3]), flag=note("keyword", True))
        elif which == 2:
            function(*note("args", []), **note("kwargs", {}))
        elif which == 3:
            function(*note("args", [1]), **note("kwargs", {"unknown": 2}))
        elif which == 4:
            function(*note("args", []), **note("kwargs", {"a": 1}))
        elif which == 5:
            function(*note("args", [1]), **note("kwargs", {1: "bad"}))
        elif which == 6:
            function(*note("args", [1]), **note("kwargs", 3))
        else:
            function(*note("args", [1, 2]), **note("kwargs", {"b": 3}), flag=note("final", True))
    except TypeError:
        print(which, "TypeError", EVENTS)

# A duplicate in a keyword merge stops subsequent groups before binding.
EVENTS.clear()
try:
    function(*note("args", [1]), **note("first", {"b": 2}), **note("duplicate", {"b": 3}), flag=note("unreached", True))
except TypeError:
    print("duplicate merge", EVENTS)

# Failure in a prior positional pack suppresses later positional groups.
EVENTS.clear()
try:
    function(*note("first", 3), *note("unreached", [1]))
except TypeError:
    print("star first", EVENTS)


def fail() -> Any:
    EVENTS.append("failure")
    raise ValueError("argument")


EVENTS.clear()
try:
    function(*fail(), flag=note("unreached", True))
except ValueError:
    print("argument first", EVENTS)
