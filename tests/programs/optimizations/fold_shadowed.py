# A parameter, local or loop variable named like the module or name a test reads (os, sys as
# system, TYPE_CHECKING as TC) hides it, so the test is not decided at compile time (issue #4,
# reproductions B and C, first); a global statement does not hide it, and holds where its branch
# is dropped. An imported module's function that takes __name__.
import os
import sys as system
from typing import TYPE_CHECKING
import typing
from typing import TYPE_CHECKING as TC
import loader.names


class OS:
    def __init__(self, name: str):
        self.name = name


def test(os: OS) -> str:
    if os.name == "posix":
        return "posix"
    return "other"


print(test(OS("nt")), test(OS("posix")))


def test_tc(TYPE_CHECKING: bool) -> str:
    if TYPE_CHECKING:
        return "yes"
    return "no"


print(test_tc(True), test_tc(False))


class P:
    def __init__(self, name: str, platform: str):
        self.name = name
        self.platform = platform


def loop(ps: list[P]) -> None:
    for os in ps:
        if os.name == "nt":
            print("loop nt")
        else:
            print("loop", os.name)


def assigned(p: P) -> str:
    os = p
    if os.name == "nt":
        return "assigned nt"
    return "assigned other"


def sysparam(system: P) -> str:
    if system.platform == "win32":
        return "win32"
    return "not win32"


def glob() -> str:
    global os
    if os.name == "nt":
        return "glob nt"
    return "glob posix"


def local_tc() -> str:
    TYPE_CHECKING = True
    if TYPE_CHECKING:
        return "tc yes"
    return "tc no"


def alias_tc(TC: bool, typing: P) -> str:
    if not TC:
        return "not"
    return "is " + typing.name


class C:
    def m(self, os: P) -> str:
        if os.name == "posix":
            return "method posix"
        return "method other"


loop([P("nt", ""), P("x", "")])
print(assigned(P("nt", "")), assigned(P("posix", "")))
print(sysparam(P("", "win32")), sysparam(P("", "linux")))
print(glob(), local_tc(), C().m(P("nt", "")), C().m(P("posix", "")))
print(alias_tc(True, P("t", "")), alias_tc(False, P("t", "")))
print([o.name == "nt" for o in [P("nt", "")]])
if system.platform == "win32" or typing.TYPE_CHECKING or TC:
    print("never")
else:
    print("posix")
print(loader.names.f("__main__"), loader.names.f("x"))
counter = 0


def bump() -> int:
    if system.platform == "win32":
        global counter  # (holds for the whole function, though its branch is dropped)
    counter = counter + 1
    return counter


print(bump(), bump(), counter)
