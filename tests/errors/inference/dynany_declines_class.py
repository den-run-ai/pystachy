# error: declines.py:13: error: unsupported call eval(str)
# pystachy: dynamic-any
# An error in a method of a class whose comparison method is declined, compiled after the
# declined methods: the pass that declines them reports it, as before (#801)
from typing import Any
from emods.declines import Bag, Ver

x: Any = Bag(1)
y: Any = Ver(1)
print(x == x, y < y)
print(Bag(2).bad())
