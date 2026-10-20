# error: nt_asdict_mixed.py:10: error: _asdict() of a NamedTuple whose fields have different types is not supported (a dict's values have one type): P
from typing import NamedTuple


class P(NamedTuple):
    x: int
    y: str


print(P(1, "a")._asdict())
