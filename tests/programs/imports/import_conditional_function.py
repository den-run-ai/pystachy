# A function's import that runs on some paths only binds a local, which a read where the import
# has not run finds unbound (CPython: UnboundLocalError). warnings._setoption() imports re under
# one test and reads it under others that imply it.
import os


def setoption(message: str, module: str) -> str:
    if message or module:
        import re
    if message:
        message = re.escape(message)
    if module:
        module = re.escape(module) + r"\Z"
    return message + "|" + module


def branch(flag: bool) -> str:
    if flag:
        import re
    return re.escape("a.b")


def from_import(flag: bool) -> str:
    if flag:
        from re import escape
    return escape("a+b")


def other_branch(flag: bool) -> str:
    if flag:
        import re
        return re.escape("c.d")
    return re.escape("e.f")


def before(flag: bool) -> str:
    # (the import makes os the function's local, though the module imports os too)
    s = os.sep if flag else ""
    from mods.units import os
    return s + os.sep


def in_loop(n: int) -> list[str]:
    out: list[str] = []
    for i in range(n):
        if i == 1:
            import fnmatch
        if i >= 1:
            out.append(fnmatch.translate("*.py"))
    return out


def after_loop(n: int) -> str:
    for i in range(n):
        import fnmatch
    return fnmatch.translate("*.txt")


def show(name: str, flag: bool) -> None:
    try:
        if name == "branch":
            r = branch(flag)
        elif name == "from_import":
            r = from_import(flag)
        elif name == "other_branch":
            r = other_branch(flag)
        elif name == "before":
            r = before(flag)
        elif name == "in_loop":
            r = str(in_loop(3 if flag else 1))
        else:
            r = after_loop(2 if flag else 0)
        print(flag, name, r)
    except UnboundLocalError as e:
        print(flag, name, "UnboundLocalError:", e)


print(setoption("a.b", ""))
print(setoption("", "x.y"))
print(setoption("", ""))
for flag in (True, False):
    for name in ("branch", "from_import", "other_branch", "before", "in_loop", "after_loop"):
        show(name, flag)
