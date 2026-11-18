# super().NAME() of a @contextmanager method of another module's class runs that class's
# generator where a subclass overrides it (#1469); the subclass's objects otherwise run their own
from contextlib import contextmanager
from typing import Iterator

from cm_super_base import Base


class Child(Base):
    @contextmanager
    def scope(self, tag: str = "t") -> Iterator[str]:
        yield "child " + tag

    def through_super(self) -> str:
        with super().scope("s") as v:
            return v


class Grandchild(Child):
    def through_both(self) -> str:
        with super().scope("g") as v:
            return v


print(Child().through_super())
with Child().scope() as w:
    print(w)
print(Grandchild().through_both())
print(Grandchild().through_super())
