# A function's import of dirname as `basename` binds a local name: posixpath.basename stays
# posixpath's own function (the loader once compiled it as the local alias, so this printed
# "/a/b /a/b").
import posixpath
from posixpath import dirname as basename


def parts(p: str) -> str:
    from posixpath import dirname as basename
    return basename(p) + " " + posixpath.basename(p)


print(parts("/a/b/c.txt"))
print(basename("/a/b/c.txt"), posixpath.basename("/a/b/c.txt"))
