# Branches of module code that CPython never runs, decided at compile time as if TYPE_CHECKING:
# blocks are: "if False:", "if 0:", and TYPE_CHECKING = False (the idiom that spares importing
# typing) tested after it, also under not/and/or, with elif and else, in the blocks of loops, try
# and with statements and after a class body. Not in a class body (tests/errors/optimizations/fold_*_class.py),
# where typing.TYPE_CHECKING still is. Their imports are never loaded (tests/loader/never.py has
# a syntax error), their defs and classes never compiled. A test before the assignment raises
# NameError; functions read the global; a flag that something rebinds is not a constant
# (tests/loader/tcset.py). Another module may assign the flag False.
import typing

import loader.tcflag
import loader.tcset


def note(s: str, v: bool) -> bool:
    print("note", s)
    return v


try:
    if TYPE_CHECKING:
        print("never")
except NameError as e:
    print(e)
TYPE_CHECKING = False
if False:
    import loader.never

    class Hidden(Unknown):
        pass
if 0:
    import pathlib
elif not False:
    print("not False")
if TYPE_CHECKING:
    import loader.never
    from collections.abc import Iterable

    def double(n: Iterable[int]) -> list[int]: ...
else:
    def double(n: int) -> int:
        return n * 2
if not TYPE_CHECKING:
    print("not TYPE_CHECKING", double(4))
if note("a", True) and TYPE_CHECKING:
    import pathlib
if TYPE_CHECKING or note("b", False):
    print("then b")
else:
    print("else b")
for i in range(2):
    if i > 0:
        print("i", i)
    elif TYPE_CHECKING:
        import loader.never


class Plain:
    if typing.TYPE_CHECKING:
        import loader.never
    k = 5


if False:
    import loader.never
n = 2
while n > 0:
    n -= 1
    if 0:
        import loader.never
    elif TYPE_CHECKING:
        import loader.never
    else:
        print("while", n)
try:
    if 00:
        import loader.never
    print("try")
finally:
    if TYPE_CHECKING or False:
        import loader.never
    print("finally")
with open("/dev/null") as f:
    if not 0:
        print("with", len(f.read()))
if not False:

    class Shown:
        k = 6

    if TYPE_CHECKING:
        import loader.never
    print("Shown", Shown.k, Plain.k)


def read() -> bool:
    return TYPE_CHECKING


def shadow(TYPE_CHECKING: bool) -> str:
    if TYPE_CHECKING:
        return "yes"
    return "no"


print(read(), shadow(True), shadow(False), TYPE_CHECKING)
loader.tcflag.TYPE_CHECKING = False
print(loader.tcflag.mode(), loader.tcflag.local(), loader.tcflag.Box(3).get(), loader.tcset.TYPE_CHECKING)
