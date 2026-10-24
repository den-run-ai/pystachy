# pystachy: dynamic-any
from graphlib import TopologicalSorter
ts = TopologicalSorter({"d": {"b", "c"}, "c": {"a"}, "b": {"a"}})
print(list(ts.static_order()))
