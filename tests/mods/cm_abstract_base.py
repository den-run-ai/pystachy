from abc import abstractmethod
from contextlib import contextmanager
from typing import Iterator


class Remote:
    @abstractmethod
    @contextmanager
    def scope(self, tag: str = "t") -> Iterator[None]:
        raise NotImplementedError("remote " + tag)
