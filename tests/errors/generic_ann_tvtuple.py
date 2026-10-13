# error: generic_ann_tvtuple.py:12: error: Row[...] is not supported for a generic class with a TypeVarTuple: only its calls' arguments bind them
from typing import Generic, TypeVarTuple

Ts = TypeVarTuple("Ts")


class Row(Generic[*Ts]):
    def __init__(self, *cells: *Ts) -> None:
        self.cells = cells


r: Row[int, str] = Row(1, "a")
print(r.cells)
