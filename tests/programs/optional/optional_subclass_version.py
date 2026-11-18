# The importlib.metadata idiom (#1504, #1438): the optional import of version() resolves, and
# version() raises PackageNotFoundError, a subclass of ModuleNotFoundError, for a package that is
# not installed, which the except clause catches as in CPython. Also a subclass of another
# module's ImportError subclass, imported under another name.
from loader.subimp.errors import Missing as Gone
import loader.subimp.errors


class Worse(loader.subimp.errors.Missing):
    pass


try:
    from loader.subimp.metadata import version

    __version__ = version("absent")
except ImportError:
    __version__ = "unknown"
print(__version__)

try:
    from loader.subimp.metadata import version

    found = version("present")
except ImportError:
    found = "unknown"
print(found)

try:
    from loader.subimp.metadata import PackageNotFoundError, version

    lost = version("absent")
except ModuleNotFoundError as e:
    lost = "not found: " + str(e)
print(lost)

try:
    import loader.subimp.errors

    name = loader.subimp.errors.require("backend", False)
except ImportError as e:
    name = f"{type(e).__name__}: {e}"
print(name)


def fails() -> str:
    raise Worse("worse")


try:
    import json

    w = fails()
except ImportError as e:
    w = f"{type(e).__name__} {isinstance(e, Gone)}"
print(w)
