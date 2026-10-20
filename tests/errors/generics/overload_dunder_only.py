# error: overload_dunder_only.py:7: error: an @overload stub of '__eq__' must be followed by the def that implements it (calling a stub raises NotImplementedError)
from typing import overload


class C:
    @overload
    def __eq__(self, o: "C") -> bool: ...


a = C()
print(a == a)
