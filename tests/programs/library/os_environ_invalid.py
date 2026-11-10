# os.environ with names an environment cannot hold. del raises os.unsetenv()'s errors before
# it looks the name up, as CPython's does: ValueError for a NUL byte, OSError (EINVAL) for no
# name or one with '=', and KeyError only for a name that is not set. A store raises
# os.putenv()'s errors; a read, get() and in find no such name
import os

NAME = "PYSTACHY_TEST_INVALID"
for name in ["", "A=B", "A\0B", "=", NAME]:
    try:
        del os.environ[name]
        print("deleted", repr(name))
    except OSError as e:
        print("OSError", e, repr(name))
    except ValueError as e:
        print("ValueError", e, repr(name))
    except KeyError as e:
        print("KeyError", e)
    try:
        os.environ[name] = "x"
        print("stored", repr(name), os.environ[name])
    except OSError as e:
        print("OSError", e, repr(name))
    except ValueError as e:
        print("ValueError", e, repr(name))
    try:
        print(os.environ[name])
    except KeyError as e:
        print("KeyError", e)
    print(name in os.environ, os.environ.get(name), os.environ.get(name, "unset"), os.environ.pop(name, "none"))
try:
    os.environ[NAME] = "a\0b"
except ValueError as e:
    print("ValueError", e, NAME in os.environ)
os.environ[NAME] = "set"
del os.environ[NAME]
try:
    del os.environ[NAME]
except KeyError as e:
    print("KeyError", e, NAME in os.environ)
