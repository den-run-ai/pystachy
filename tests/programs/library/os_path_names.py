# os.path's string functions, which are posixpath's in CPython: basename, dirname, split,
# splitext, isabs, normpath, abspath, relpath, expanduser and commonprefix, by each way of naming
# them and as values, with os.path's constants and CPython's errors
import os
import os.path
import os.path as osp
from os import path
from os.path import basename, dirname, pardir, sep, splitext

PATHS = ["/a/b/c.txt", "a/b/", "", "/", "//", "///", "//x//y/../z/.", "../../a/./b/..", "~", "c.tar.gz", ".bashrc", "a/.b.c",
         "..", "x/..x.y", "é/ü.py", "a b/c d.e f", "/a/b/../../../c", "a/b.c/d", "...", "a."]
for p in PATHS:
    print(repr(p), repr(basename(p)), repr(dirname(p)), os.path.split(p), splitext(p), osp.isabs(p), repr(path.normpath(p)))
cwd = os.getcwd()
print(os.path.abspath("x/../y") == os.path.join(cwd, "y"), os.path.abspath("") == cwd, os.path.abspath("/a/./b//c/.."), os.path.abspath("//a/../b"))
print(os.path.relpath("/a/b/c", "/a/d"), os.path.relpath("/a/b/c", start="/a/b/c"), os.path.relpath("/", "/x/y"), os.path.relpath("//a", "/"))
print(os.path.relpath(cwd + "/q/r"), os.path.relpath(cwd), os.path.relpath("q", "."), os.path.relpath("q/../r", ""), os.path.relpath("a", "a/b/c"))
print(repr(os.path.commonprefix(["/usr/lib", "/usr/local", "/usr/libexec"])), repr(os.path.commonprefix(["é1", "é2", "éx"])), repr(os.path.commonprefix(["aé", "aè"])))
none: list[str] = []
print(repr(os.path.commonprefix(none)), repr(os.path.commonprefix(["abc"])), repr(os.path.commonprefix(["ab", "abc", "a"])), repr(os.path.commonprefix(["", "a"])))
print(sep, pardir, os.path.curdir, os.path.extsep, os.path.pathsep, os.path.devnull, os.path.sep == os.sep)
os.environ.__setitem__("HOME", "/h/me//")
print(os.path.expanduser("~"), os.path.expanduser("~/x/y"), os.path.expanduser("a/~"), repr(os.path.expanduser("")), os.path.expanduser("~nosuchuser_pystachy_test/x"))
os.environ.__setitem__("HOME", "")
print(os.path.expanduser("~"), os.path.expanduser("~/x"))
os.environ.pop("HOME", "")
home = os.path.expanduser("~")  # (the password database's entry for this user, or "~" where it has none)
print(home == "~" or (os.path.isabs(home) and (home == "/" or not home.endswith("/"))), os.path.expanduser("~/x") == ("~/x" if home == "~" else home.rstrip("/") + "/x"))
names = list(map(os.path.basename, PATHS[:4]))
exts = [splitext(p)[1] for p in PATHS]
head, tail = os.path.split("/usr/local/bin")
print(names, exts, head, tail, sorted(PATHS, key=os.path.basename)[:3])
try:
    os.path.relpath("")
except ValueError as e:
    print("ValueError", e)
try:
    os.path.expanduser("~a\0b/x")
except ValueError as e:
    print("ValueError", e)
