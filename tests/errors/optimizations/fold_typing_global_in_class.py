# error: fold_typing_global_in_class.py:13: error: a class body may only contain fields, methods, a docstring, pass and ..., not a global statement
# A global statement holds for the whole class body, also in a branch that CPython does not run
# (here typing's TYPE_CHECKING, which Pystachy decides at compile time): x = 2 binds the module's x,
# and CPython prints 2. The statement is kept when its branch is dropped, and a class body may not
# hold one (fold_flag_in_class.py).
from typing import TYPE_CHECKING

x = 1


class C:
    if TYPE_CHECKING:
        global x
    x = 2


print(x)
