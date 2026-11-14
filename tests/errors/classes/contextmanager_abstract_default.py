# error: unsupported decorator @contextmanager
# An abstract @contextmanager method whose default is no literal: its parameters would be those
# of two methods, which would evaluate the default twice
from abc import abstractmethod
from contextlib import contextmanager
from typing import Iterator


def default() -> int:
    print("default evaluated")
    return 3


class Api:
    @abstractmethod
    @contextmanager
    def scope(self, n: int = default()) -> Iterator[None]:
        raise NotImplementedError("n=" + str(n))


print(Api() is not None)
