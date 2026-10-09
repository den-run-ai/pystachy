# error: 'x' is local to f() only through code that is dropped at compile time (for the platform, TYPE_CHECKING or an import that fails), so a read of it raises UnboundLocalError; that is supported only where the dropped code annotates it with a supported type or assigns it a constant
import sys

x = 5


def f() -> int:
    if sys.platform == "win32":
        x = len(sys.argv)
    return x


print(f())
