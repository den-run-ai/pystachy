# error: unsupported decorator @contextmanager
# An abstract @contextmanager method that yields values: no generator stands for it
from abc import abstractmethod
from contextlib import contextmanager
from typing import Iterator


class Api:
    @abstractmethod
    @contextmanager
    def scope(self) -> Iterator[int]:
        raise NotImplementedError


print(Api() is not None)
