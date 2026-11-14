# pystachy: dynamic-any
# x.__init__(*args) of a complex number held as an Any value, or a call of its bound __init__ with
# unpacked arguments, is object.__init__ as a direct call is (dynany_complex_init.py): it ignores
# the arguments and returns None, leaving x, and a dict's key that holds it, as they are
from typing import Any

x: Any = 1j
args: list[Any] = [2.0, 4.0]
kws: dict[str, Any] = {}
d: dict[Any, str] = {x: "k"}
print(x.__init__(*args), x)
print(x.__init__(*args, **kws), x)
m = x.__init__
print(m(*args), x)
print(x, d[1j], x in d, hash(x) == hash(1j))
y: Any = complex(3, 4)
print(y.__init__(*[]), y)
