# Documented deviation: Path.expanduser() of ~user, and Path.open() with buffering, errors or
# newline, raise UnsupportedOperation (lib/compatibility.md#pathlib), where CPython expands the
# user's home directory (or raises RuntimeError for an unknown user, as here) and opens the file
from pathlib import Path, UnsupportedOperation

try:
    print(Path("~no_such_user_here/x").expanduser())
except UnsupportedOperation as e:
    print("UnsupportedOperation:", e)
except RuntimeError as e:
    print("RuntimeError:", e)
try:
    with Path("/dev/null").open(newline="") as f:
        print(repr(f.read()))
except UnsupportedOperation as e:
    print("UnsupportedOperation:", e)
print(issubclass(UnsupportedOperation, NotImplementedError))
