# pystachy: dynamic-any
from typing import Any

cont: Any = {}
cont["k"] = {}
cont["k"]["x"] = 1
print(cont)
