# pystachy: dynamic-any
# In a module that opts in to dynamic Any, type(1j) is complex's class value, as type(range(1)) is
# range's: the one object that the name complex gives as a value
from typing import Any

k = type(1j)
print(k, k is complex, k == complex)
a: Any = k
print(a is complex, a == type(2j))
reg: dict[Any, str] = {complex: "c", int: "i"}
print(reg[type(1j)], reg[type(1)])
