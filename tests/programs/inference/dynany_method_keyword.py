# pystachy: dynamic-any
# A method call through an Any value takes keyword arguments (#774), here list.sort()'s, as
# typed code's does (dynany_call_keywords has the others). Compile-time error before #774.
from typing import Any

v: Any = [3, 1, 2]
v.sort(reverse=True)
print(v)
v.sort(reverse=False, key=lambda x: x % 3)
print(v)
