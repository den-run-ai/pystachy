"""Task[T] of another module's generic Fut[T] (tests/programs/classes/generic_bases_modules.py)."""
from typing import TypeVar

from hiermods import futs

T = TypeVar("T")


class Task(futs.Fut[T]):
    def __init__(self, value: T, steps: int) -> None:
        super().__init__(value)
        self.steps = steps

    def kind(self) -> str:
        return "task " + repr(self.value) + " " + str(self.steps)
