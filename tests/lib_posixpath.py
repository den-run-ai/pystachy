# CPython's own Lib/posixpath.py and Lib/genericpath.py (lib/, unmodified): the path string
# functions. (join, relpath, commonpath, commonprefix, abspath, expanduser need try, *args or
# map; exists and the other file tests need try.)
import posixpath
from posixpath import basename, dirname, normpath

paths = ["/usr/lib/python3.13/os.py", "relative/dir/", "", "/", "//", "///x//y/", "a/./b/../c", "../../up", "file.tar.gz",
         ".hidden", "..", ".", "/a/b/.../c", "no_ext", "dir.d/file", "C:\\\\win\\\\path"]
for p in paths:
    print(repr(p), posixpath.normcase(p), posixpath.isabs(p), posixpath.split(p), posixpath.splitext(p), posixpath.splitdrive(p))
    print("   ", posixpath.splitroot(p), basename(p), dirname(p), normpath(p))
print(posixpath.sep, posixpath.curdir, posixpath.pardir, posixpath.extsep, posixpath.pathsep, posixpath.defpath, posixpath.devnull, posixpath.altsep)
print(posixpath.supports_unicode_filenames, len(posixpath.__all__))
