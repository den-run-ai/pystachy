# Classes whose @contextmanager methods subclasses in another module override
# (tests/programs/classes/contextmanager_super_module*.py)
from contextlib import contextmanager
from typing import Iterator


class Base:
    @contextmanager
    def scope(self, tag: str = "t") -> Iterator[str]:
        yield "base " + tag


class Counted:
    def __init__(self) -> None:
        self.n = 0

    @contextmanager
    def bump(self, by: int = 1) -> Iterator[int]:
        self.n += by
        try:
            yield self.n
        finally:
            self.n -= by
