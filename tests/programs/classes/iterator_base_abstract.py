# A class deriving from Iterator[...] is made by ABCMeta: an abstract method it leaves without an
# implementation keeps its objects from being made, as abc.ABC's subclasses' are
from abc import abstractmethod
from typing import Iterator


class Steps(Iterator[int]):
    def __init__(self) -> None:
        self.n = 2

    def __iter__(self) -> "Steps":
        return self

    def __next__(self) -> int:
        if self.n == 0:
            raise StopIteration
        self.n -= 1
        return self.n

    @abstractmethod
    def required(self) -> int: ...


class Done(Steps):
    def required(self) -> int:
        return 7


try:
    Steps()
    print("made")
except TypeError as e:
    print(e)
d = Done()
print(list(d), d.required())
