# A module-level name that x: Any declares without a value binds nothing, as in CPython: its
# assignments type it as if unannotated (mypy's orjson: Any before an optional import).
import typing
from typing import Any

fast: Any
try:
    import pystachy_no_such_module as fast  # type: ignore[no-redef]
except ImportError:
    fast = None

count: Any
count = 3
names: typing.Any
if count > 1:
    names = ["a", "b"]
else:
    names = []


def dumps(x: int) -> str:
    if fast is not None:
        return "fast"
    return str(x)


print(dumps(count), fast is None, names)
