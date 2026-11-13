from collections import ChainMap
c = ChainMap({"a": 1}, {"a": 2, "b": 3})
print(c["a"], c["b"], len(c), sorted(c))
