from types import MappingProxyType

M = MappingProxyType({"a": "x"})
print(M["a"], len(M), "a" in M)
