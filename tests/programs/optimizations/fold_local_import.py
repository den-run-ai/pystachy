# A function's own import of sys, os or TYPE_CHECKING (also one the module repeats): after it,
# also in a nested block, the function's tests of the platform and of TYPE_CHECKING are decided
# as the module's are, so the imports they guard are dropped.
import sys
from typing import TYPE_CHECKING


def g() -> None:
    import sys
    if sys.platform == "win32":
        import winreg
    print("g", sys.platform == "win32")


def f() -> None:
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        import nonexistent_mod
    print("f", TYPE_CHECKING)


def h(flag: bool) -> str:
    import os as _os
    if flag and _os.name == "nt":
        import nt
    return _os.name


def k(n: int) -> str:
    if n > 0:
        import sys
        if sys.platform.startswith("win"):
            import winreg
    return "k"


g()
f()
print(h(True), k(1), sys.platform == "win32", TYPE_CHECKING)
