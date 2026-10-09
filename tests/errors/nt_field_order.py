# error: nt_field_order.py:7: error: Non-default namedtuple field b cannot follow default field a
from typing import NamedTuple


class Pair(NamedTuple):
    a: int = 0
    b: int
