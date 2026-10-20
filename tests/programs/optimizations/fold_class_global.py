# A global statement in code dropped at compile time still holds for its own scope, as in CPython:
# a method's under "if TYPE_CHECKING:" is the method's (and the class's x = 2 binds a class
# attribute), and one in a method's dropped branch makes the method's x = 3 bind the module's x.
# (In a class body itself, it is an error: errors/fold_typing_global_in_class.py.)
from typing import TYPE_CHECKING

x = 1


class C:
    if TYPE_CHECKING:

        def f(self) -> None:
            global x
            x = 5

    x = 2

    def g(self) -> int:
        if TYPE_CHECKING:
            global x
        x = 3
        return x


print(x, C.x, C().g(), x)
