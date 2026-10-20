# error: TypeVarTuple 'Ts' is only supported unpacked (*Ts), in tuple[...], Callable[[...], R] and *args
from typing import Generic, TypeVarTuple

Ts = TypeVarTuple("Ts")


class Row(Generic[*Ts]):
    def __init__(self, *cells: *Ts) -> None:
        self.cells: Ts = cells


print(Row(1, 2).cells)
