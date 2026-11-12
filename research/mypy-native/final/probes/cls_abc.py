from abc import ABC, abstractmethod
from typing import Final
class A(ABC):
    K: Final = [1]
    N: Final = 2
    @abstractmethod
    def f(self) -> int: ...
class I(A):
    def f(self) -> int:
        return len(self.K) + self.N
print(I().f())
