# pystachy: dynamic-any
# An int literal's box is one object per module, as CPython's constants are one per compiled module
# (#797): a module's equal literals are one object, also those of its functions; two modules', or a
# module's and the main program's, are two
from typing import Any

import mods.dynlit_a as a
import mods.dynlit_b as b

mine: Any = 1000


def show(label: str, x: Any, y: Any) -> None:
    print(label, x is y, x is not y, id(x) == id(y))


show("one module:", a.big, a.big_again())
show("two modules:", a.big, b.big)
show("two modules' functions:", a.big_again(), b.big_again())
show("main and a module:", mine, a.big)
