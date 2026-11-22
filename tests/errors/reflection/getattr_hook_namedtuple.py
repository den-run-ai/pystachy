# error: getattr_hook_namedtuple.py:9: error: the special method __getattr__ is not supported (CPython calls it for each attribute it does not find) in a NamedTuple or an enum
# Pystachy calls the __getattr__ of an ordinary class or a dataclass (#1536), not a NamedTuple's.
from typing import NamedTuple


class Point(NamedTuple):
    x: int

    def __getattr__(self, name: str) -> int:
        return 0


print(Point(1).y)
