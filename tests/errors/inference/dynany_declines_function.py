# error: declines.py:30: error: unsupported call eval(str)
# pystachy: dynamic-any
# An error in a function outside any class, compiled after the declined comparison methods: the
# pass that declines them reports it, as before (#801)
from typing import Any
from emods.declines import Bag, Ver, broken

x: Any = Bag(1)
y: Any = Ver(1)
print(x == x, y < y)
print(broken())
