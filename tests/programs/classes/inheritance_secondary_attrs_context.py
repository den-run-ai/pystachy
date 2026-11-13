# A secondary base's @contextmanager method saves and restores an attribute the base declares,
# as mypy's SplittingVisitor.set_recurse_into_functions does for three unrelated visitors.
from contextlib import contextmanager
from typing import Iterator


class Splitting:
    recurse: bool

    @contextmanager
    def recursing(self) -> Iterator[None]:
        old = self.recurse
        self.recurse = True
        try:
            yield
        finally:
            self.recurse = old


class Visitor:
    def __init__(self, name: str) -> None:
        self.name = name


class Checker(Visitor, Splitting):
    def __init__(self) -> None:
        super().__init__("checker")
        self.recurse = False
        self.log: list[str] = []

    def run(self) -> None:
        with self.recursing():
            self.log.append(self.name + ":" + str(self.recurse))
        self.log.append(self.name + ":" + str(self.recurse))


class Stripper(Visitor, Splitting):
    def __init__(self) -> None:
        self.depth = 3
        super().__init__("stripper")
        self.recurse = False


def within(s: Splitting) -> list[bool]:
    out = [s.recurse]
    with s.recursing():
        out.append(s.recurse)
        try:
            with s.recursing():
                raise ValueError("stop")
        except ValueError:
            out.append(s.recurse)
    out.append(s.recurse)
    return out


c = Checker()
c.run()
print(c.log, within(c), within(Stripper()))
