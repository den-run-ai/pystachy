# Documented deviation (lib/compatibility.md#types): a mapping proxy compared with an object of
# another class is not equal to it, where CPython compares the proxy's dict with the object, so
# that the object's own __eq__, given the dict, decides (CPython prints True False False). A dict
# compared with such an object is a compile-time error in Pystachy, and the proxy's == does not
# run the object's method.
from types import MappingProxyType


class AnyDict:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, dict)


m = MappingProxyType({"x": 1})
a = AnyDict()
print(m == a, m != a, a == m)
