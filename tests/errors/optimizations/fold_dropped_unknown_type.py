# error: fold_dropped_unknown_type.py:15: error: 'b' is local to f() only through code that is dropped at compile time
# The dropped code annotates the local with a type that only TYPE_CHECKING imports.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foo import Bar


def make() -> int:
    return 1


def f(flag: bool) -> int:
    if TYPE_CHECKING:
        b: Bar = make()
    if flag:
        return b.x
    return 0


print(f(False))
