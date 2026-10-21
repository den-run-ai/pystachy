# error: dynany_declines_before.py:10: error: unsupported call eval(str)
# pystachy: dynamic-any
# An error compiled before the comparison methods that would be declined: the first pass reports
# it, as before (#801)
from typing import Any
from emods.declines import Bag, Ver


def early() -> int:
    return eval("4")


x: Any = Bag(1)
y: Any = Ver(1)
print(x == x, y < y, early())
