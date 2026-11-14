# error: unsupported decorator @contextmanager
# An abstract @contextmanager method whose body could return: CPython's helper would keep its
# None as the generator and raise TypeError where the with statement enters it
from abc import abstractmethod
from contextlib import contextmanager
from typing import Iterator


class Api:
    @abstractmethod
    @contextmanager
    def scope(self) -> Iterator[None]:
        ...


print(Api() is not None)
