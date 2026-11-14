# A @contextmanager method whose parameter for the object is named as its class: the method
# that the loader writes still calls the class's generator, not the object's attribute
from contextlib import contextmanager
from typing import Iterator


class C:
    @contextmanager
    def scope(C) -> Iterator[int]:
        yield 42


with C().scope() as v:
    print(v)
