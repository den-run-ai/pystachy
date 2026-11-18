# An override of another module's @contextmanager method that enters super().NAME() in its own
# generator: the base class's generator runs there, not the override again (#1469)
from contextlib import contextmanager
from typing import Iterator

from cm_super_base import Counted


class More(Counted):
    @contextmanager
    def bump(self, by: int = 1) -> Iterator[int]:
        with super().bump(by * 10) as n:
            yield n + 1


m = More()
with m.bump(2) as k:
    print(k, m.n)
print(m.n)
