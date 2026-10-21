# error: nt_field_defaults.py:10: error: P._field_defaults is not supported (of a typing.NamedTuple class)
from typing import NamedTuple


class P(NamedTuple):
    x: int
    y: int = 0


print(P._field_defaults)
