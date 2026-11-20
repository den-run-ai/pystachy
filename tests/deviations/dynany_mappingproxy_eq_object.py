# pystachy: dynamic-any
# Documented deviation (lib/compatibility.md#types): a mapping proxy held as an Any value and
# compared with an object of another class lets the object's own __eq__ answer, as CPython's
# does, but gives that method the proxy, where CPython gives it the proxy's dict (CPython prints
# True False False). Typed code has the same answer (lib_types_mappingproxy_eq_other.py).
from types import MappingProxyType
from typing import Any


class AnyDict:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, dict)


m: Any = MappingProxyType({"x": 1})
a: Any = AnyDict()
print(m == a, m != a, a == m)
