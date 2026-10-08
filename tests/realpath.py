# os.path.realpath: absolute, normalized, symbolic links resolved one component at a time (a link
# that leads back to itself, or to nothing, stays as it is); a path that does not exist is kept as
# far as it does not. The links are in tests/linked/. An embedded NUL raises ValueError.
import os
from os.path import realpath

cwd = os.path.realpath(".")


def rel(p: str) -> str:
    r = os.path.realpath(p)
    return "<cwd>" + r[len(cwd) :] if r.startswith(cwd) else r


print(cwd.startswith("/"), os.path.realpath(cwd) == cwd, realpath("") == cwd)
print(realpath("/"), realpath("/.."), realpath("//no-such-x"), realpath("///no-such-x/../y"), realpath("/no-such-x/a/./b/../c/"))
print(rel("."), rel("tests/../tests"), rel("no/such/../file"), rel("tests//./realpath.py"))
print(rel("tests/symlink_main.py"), rel("tests/linked/sub/helper.py"), rel("tests/linked/sub/../realpath.py"))
print(rel("tests/linked/loop1"), rel("tests/linked/loop2/x"), rel("tests/linked/dangling/x/.."))
print(rel("tests/linked/sub/../../tests/linked/loop1/.."))
print(realpath("a\0b"))
