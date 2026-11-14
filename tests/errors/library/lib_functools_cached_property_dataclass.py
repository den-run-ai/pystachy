# error: lib_functools_cached_property_dataclass.py:11: error: @cached_property method A.v() of a dataclass is not supported
from dataclasses import dataclass
from functools import cached_property


@dataclass
class A:
    n: int

    @cached_property
    def v(self) -> int:
        return self.n * 2


print(A(2).v)
