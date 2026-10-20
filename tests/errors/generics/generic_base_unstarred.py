# error: a generic class's one base is Generic[...] of its TypeVars, and at most one TypeVarTuple, unpacked (Generic[T, *Ts]), each once
from typing import Generic, TypeVarTuple

Ts = TypeVarTuple("Ts")


class Row(Generic[Ts]):
    def __init__(self, n: int) -> None:
        self.n = n


print(Row(1).n)
