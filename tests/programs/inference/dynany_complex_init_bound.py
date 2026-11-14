# pystachy: dynamic-any
# A call of the bound __init__ of a complex number held as an Any value, m = x.__init__, is
# object.__init__ as x.__init__(...) is (dynany_complex_init.py): it takes any arguments, by
# position or keyword, returns None and leaves x, and a dict's key that holds it, as they are
from typing import Any

x: Any = 1j
d: dict[Any, str] = {x: "k"}
m = x.__init__
print(m(), x)
print(m(2.0, 4.0), x)
print(m(real=1.0), x)
print(x, d[1j], x in d)
