# pystachy: dynamic-any
# Existing Callable adapters erase the wrapped object's original class identity.
from typing import Any, Callable

typed: Callable[[str], int] = int
value: Any = typed
print(value("7"))
try:
    cls = type(value)
    print(cls.__name__)
except NotImplementedError as exc:
    print(str(exc))
