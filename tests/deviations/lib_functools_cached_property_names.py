# Documented deviation: each @cached_property method adds names that dir() and hasattr() see
# (lib/compatibility.md#functools): _pys_cpget_NAME, the method, and the fields _pys_cpset_NAME
# and _pys_cpval_NAME, which keep its value. CPython keeps the value in the object's __dict__
# as NAME.
from functools import cached_property


class A:
    def __init__(self, n: int) -> None:
        self.n = n

    @cached_property
    def x(self) -> int:
        return self.n * 2


a = A(3)
print([k for k in dir(a) if not k.startswith("__")])
print(hasattr(a, "_pys_cpget_x"), a.x)
