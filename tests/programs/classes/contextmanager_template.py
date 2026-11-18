# @contextmanager methods of a class template (an __init__ parameter without an annotation): each
# specialization makes its own class's generator
from contextlib import contextmanager
from typing import Iterator


class C:
    def __init__(self, n):
        self.n = n

    @contextmanager
    def scope(self) -> Iterator[str]:
        yield "c " + str(self.n)


with C(42).scope() as a, C("xy").scope() as b:
    print(a, b)
