# Tests of the platform that Pystachy decides at compile time, as CPython makes them when the code
# runs: sys.platform == or != a str, in a tuple, startswith() of a str or a tuple of them, os.name
# == or !=, sys.implementation.name == or != (under not, and, or), in if and elif tests, in
# conditional expressions, in a function, and through a module-level name assigned such a test
# once. A branch that does not run is not compiled: it may import a module that does not exist or
# hold code Pystachy rejects, as CPython runs neither
import os
import sys

if sys.platform == "win32":
    import nt
    print("windows")
elif sys.platform.startswith(("linux", "darwin", "freebsd")):
    print("a POSIX platform")
else:
    import missing_platform_module
if sys.platform != "cygwin" and not sys.platform.startswith("win"):
    print("not cygwin or windows")
if os.name == "nt" or sys.platform in ("win32", "cygwin", "msys"):
    import winreg
    x: int = "not an int"
if os.name != "posix":
    raise SystemExit("not posix")
if sys.implementation.name == "jython" or sys.implementation.name == "ironpython":
    import java.lang
if sys.implementation.name != "graalpy":
    print("not graalpy")

_MS_WINDOWS = (sys.platform == 'win32')
if _MS_WINDOWS:
    import nt as _os
else:
    import os as _os
if not _MS_WINDOWS:
    print("separator", _os.sep)

SEP = "\\" if sys.platform == "win32" else "/"
KIND = "jvm" if sys.implementation.name == "jython" else "native"


def describe() -> str:
    if sys.platform.startswith("win"):
        import msvcrt
        return "windows"
    return "posix" if os.name == "posix" else "other"


print(SEP, KIND, describe(), _MS_WINDOWS)
