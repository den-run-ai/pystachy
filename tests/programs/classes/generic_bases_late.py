# A specialization of a generic class with a base, first made where module code runs after a
# call through the base was compiled (show(Base) dispatches on b.kind()): the next pass makes the
# specializations before any code compiles (templates.py's gspec_replay), so that the dispatch
# selects their overrides; without it, it ran Fut[int]'s kind() for a Task[str].
from typing import Generic, TypeVar

T = TypeVar("T")


class Base:
    def __init__(self, name: str) -> None:
        self.name = name

    def kind(self) -> str:
        return "base " + self.name


class Fut(Base, Generic[T]):
    def __init__(self, name: str, value: T) -> None:
        super().__init__(name)
        self.value = value

    def kind(self) -> str:
        return "fut " + self.name + " " + str(self.value)


class Task(Fut[T]):
    def __init__(self, value: T) -> None:
        super().__init__("task", value)

    def kind(self) -> str:
        return "task " + str(self.value)


def show(b):
    print(b.kind(), isinstance(b, Fut), isinstance(b, Task))


show(Base("b"))
x: Base = Fut("f", 3)
show(x)
y: Base = Task("s")
show(y)
z: Base = Fut("g", [1, 2])
show(z)
w: Base = Task(2.5)
show(w)
