# Generic classes with a base: class Fut(Base, Generic[T]) and class Fut[T](Base) derive from an
# ordinary class, and class Task(Fut[T]) and class Task[T](Fut[T]) from a generic class with
# their own type variables (asyncio's Task derives from Future so). Each specialization is a
# subclass of its base's (Task[int] of Fut[int]): its objects begin with the base's fields,
# super().__init__() initializes them, inherited methods work on them, overrides win in calls
# through any base, and isinstance() sees the whole hierarchy, also through a list of the
# ordinary base holding objects of several specializations.
from typing import Generic, TypeVar

T = TypeVar("T")


class Base:
    def __init__(self, name: str) -> None:
        self.name = name
        self.done = False

    def finish(self) -> None:
        self.done = True

    def describe(self) -> str:
        return f"{self.name}: done={self.done}"

    def kind(self) -> str:
        return "base"


class Fut(Base, Generic[T]):
    def __init__(self, name: str, value: T) -> None:
        super().__init__(name)
        self.value = value

    def get(self) -> T:
        return self.value

    def kind(self) -> str:
        return "fut"


class Task(Fut[T]):
    def __init__(self, name: str, value: T, steps: int) -> None:
        super().__init__(name, value)
        self.steps = steps

    def kind(self) -> str:
        return "task " + str(self.steps)

    def describe(self) -> str:
        return "Task " + super().describe()


class Pep[T](Base):
    def __init__(self, item: T) -> None:
        super().__init__("pep")
        self.item = item


class PepTask[T](Pep[T]):
    def __init__(self, item: T, extra: T) -> None:
        super().__init__(item)
        self.extra = extra

    def pair(self) -> list[T]:
        return [self.item, self.extra]


def show(b: Base) -> None:
    print(b.kind(), b.describe(), isinstance(b, Fut), isinstance(b, Task), isinstance(b, Pep))


f = Fut("f", 3)
t = Task("t", "s", 2)
n = Task("n", None, 0)
p = PepTask(1.5, 2.5)
items: list[Base] = [Base("b"), f, t, n, Pep("x"), p]
for b in items:
    show(b)
t.finish()
print(f.get() + 1, t.get().upper(), n.get(), t.describe(), p.pair(), p.done)
print(isinstance(t, Fut), isinstance(f, Task), isinstance(t, Base))


def last(fs: list[Base]) -> Base:
    return fs[-1]


x = last(items)
if isinstance(x, Pep):
    print("pep", x.name)
