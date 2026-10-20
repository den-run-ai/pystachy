# del of a function's local that has the name of an import, a function or a class of the
# module: the local hides them, so it is a variable, and a read after del raises
# UnboundLocalError.
import os


def helper() -> int:
    return 1


class C:
    pass


def f() -> str:
    os = "local"
    print(os)
    del os
    helper = 2
    del helper
    C = 3.5
    del C
    print(os)
    return "deleted"


print(helper(), os.sep)
print(f())
