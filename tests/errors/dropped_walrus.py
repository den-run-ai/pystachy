# error: 'x' is local to f() only through code that is dropped at compile time
# x := in a comprehension in a TYPE_CHECKING block, which CPython never runs, still makes x a local
# of f that nothing binds (CPython: UnboundLocalError), not the module's x.
from typing import TYPE_CHECKING

x = 3


def f() -> int:
    if TYPE_CHECKING:
        print([(x := i) for i in range(2)])
    return x


print(f())
