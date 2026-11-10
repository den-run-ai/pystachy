# os.environ[name] reads, assignments and del, os.environ.get() and name in os.environ: the
# process's environment, which os.getenv() reads too, with CPython's KeyError for a name it has not
import os

NAME = "PYSTACHY_TEST_ENVIRON"
print(NAME in os.environ, NAME not in os.environ, os.environ.get(NAME), os.environ.get(NAME, "unset"), os.getenv(NAME))
os.environ[NAME] = "one"
print(NAME in os.environ, os.environ[NAME], os.environ.get(NAME), os.environ.get(NAME, "unset"), os.getenv(NAME))
os.environ[NAME + "_2"] = os.environ[NAME] + " two é"
os.environ[NAME] = ""
print(repr(os.environ[NAME]), os.environ[NAME + "_2"], len(os.environ[NAME + "_2"]), (os.environ.get(NAME) or "empty"))
del os.environ[NAME]
print(NAME in os.environ, os.environ.get(NAME) is None, os.environ.pop(NAME + "_2", "gone"), os.environ.pop(NAME + "_2", "gone"))
for name in [NAME, "", "A=B"]:
    try:
        print(os.environ[name])
    except KeyError as e:
        print("KeyError", e)
try:
    del os.environ[NAME]
except KeyError as e:
    print("KeyError", e)


def home_or(default: str) -> str:
    value = os.environ.get("PYSTACHY_TEST_HOME")
    return value if value is not None else default


os.environ["PYSTACHY_TEST_HOME"] = "/h"
print(home_or("?"), "PYSTACHY_TEST_HOME" in os.environ and os.environ["PYSTACHY_TEST_HOME"] == "/h")
del os.environ["PYSTACHY_TEST_HOME"]
print(home_or("?"))
