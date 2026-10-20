# A mapping proxy has no attributes of its own, as CPython's C object has none: hasattr() of the
# field that holds its dict, or of __dict__, is false, and __init__ (object's, which takes any
# arguments) leaves the proxy viewing the dict it was made with
from types import MappingProxyType

d = {"a": 1}
m = MappingProxyType(d)
print(hasattr(m, "_mapping"), hasattr(m, "__dict__"), hasattr(m, "get"), hasattr(m, "copy"))
m.__init__({"b": 2})
print(m, d)
m.__init__({"c": 3}, 4, key=5)
d["z"] = 26
print(m, len(m), "c" in m)
