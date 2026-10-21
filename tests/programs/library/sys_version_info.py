# sys.version_info (#6, #252): CPython 3.13.16's (.python-version), a tuple of its items for
# comparisons, indexing, slicing, unpacking, formatting and default values (warnings's
# _deprecated(_version=sys.version_info)), its attributes, also through from sys import
# version_info; and comparisons of it with literals that decide an if statement at compile
# time, as CPython decides it at import time, so that the branch not taken may hold Python 2
# code, in module code, functions and under not/and/or (with the other operands still run)
import sys
import sys as _sys
from sys import version_info

print(sys.version_info >= (3, 8), sys.version_info < (3,), sys.version_info[:2] == (3, 13), sys.version_info[:2] != (3, 12))
print(sys.version_info[0], sys.version_info[-2], sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
print(sys.version_info.releaselevel, sys.version_info.serial, len(sys.version_info), sys.version_info[3:1])
print(sys.version_info[:3], sys.version_info[1:], sys.version_info[-3:-1], sys.version_info[-9:2], sys.version_info[:])
print("%d.%d" % sys.version_info[:2], f"{sys.version_info[0]}.{sys.version_info[1]}", "%d.%d.%d" % sys.version_info[:3])
major, minor, micro, level, serial = sys.version_info
print(major, minor, level, serial, version_info.major, version_info[:2] >= (3, 11))
print(version_info >= (3, 13, 16, "final"), version_info > (3, 13, 16, "final", 0), version_info < (3, 13, 16, "zeta"))


def deprecated(name, remove, _version=sys.version_info):
    # warnings._deprecated's test of its _version
    if (_version[:2] > remove) or (_version[:2] == remove and _version[3] != "alpha"):
        return f"{name!r} was slated for removal after Python {remove[0]}.{remove[1]} alpha"
    return f"{name!r} is deprecated and slated for removal in Python {remove[0]}.{remove[1]}"


print(deprecated("x", (3, 12)))
print(deprecated("y", (3, 15)))
print(deprecated("z", (3, 13)))

if sys.version_info < (3,):
    text_type = unicode  # noqa: F821 (Python 2's, never compiled)
    from itertools import izip
elif sys.version_info >= (3, 14):
    text_type = bytes
else:
    text_type = str
print(text_type(5))

calls: list[str] = []


def effect(x: bool) -> bool:
    calls.append(str(x))
    return x


if _sys.version_info[0] == 2 or not _sys.version_info.minor >= 10:
    import cPickle as pickle
    print(pickle)
elif effect(True) and _sys.version_info < (3, 0):
    import cPickle as pickle
    print(pickle)
elif effect(False) or _sys.version_info[:2] > (3, 12) and _sys.version_info[3] == "final":
    print("3.13", calls)


def python2() -> str:
    if sys.version_info.major < 3:
        return basestring  # noqa: F821
    elif sys.version_info[0] != 3 or sys.version_info[:1] < (3,):
        return long  # noqa: F821
    return "py3"


print(python2())
