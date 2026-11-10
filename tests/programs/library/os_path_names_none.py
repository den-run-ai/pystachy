# os.path's string functions raise CPython's TypeError for a path that is None, as os.fspath()
# does for it first
import os

missing = os.getenv("PYSTACHY_NO_SUCH_VAR")
try:
    print(os.path.basename(missing))
except TypeError as e:
    print("basename", e)
try:
    print(os.path.dirname(missing))
except TypeError as e:
    print("dirname", e)
try:
    print(os.path.split(missing))
except TypeError as e:
    print("split", e)
try:
    print(os.path.splitext(missing))
except TypeError as e:
    print("splitext", e)
try:
    print(os.path.isabs(missing))
except TypeError as e:
    print("isabs", e)
try:
    print(os.path.normpath(missing))
except TypeError as e:
    print("normpath", e)
try:
    print(os.path.abspath(missing))
except TypeError as e:
    print("abspath", e)
try:
    print(os.path.expanduser(missing))
except TypeError as e:
    print("expanduser", e)
os.environ.__setitem__("PYSTACHY_TEST_PATH", "/x//y.z")
present = os.getenv("PYSTACHY_TEST_PATH")  # (a str | None that holds a str)
print(os.path.isabs(present), os.path.split(present), os.path.splitext(present), os.path.dirname(present), os.path.normpath(present))
