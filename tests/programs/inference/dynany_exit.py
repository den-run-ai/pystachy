# pystachy: dynamic-any
# Context managers whose __exit__ takes Any parameters (*args: Any, or exc_type: Any, exc: Any,
# tb: Any), the usual annotations, in a module that compiles typing.Any as dynamic values: a with
# statement passes them an exception class and an exception, which they take as in modules that do
# not opt in (#782); they suppress the exception where __exit__ returns a true value.
from typing import Any


class Quiet:
    def __enter__(self) -> "Quiet":
        print("enter")
        return self

    def __exit__(self, *args: Any) -> None:
        print("exit", args[0] is None)


class Swallow:
    def __init__(self, keep: bool) -> None:
        self.keep = keep

    def __enter__(self) -> "Swallow":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        print("exit", exc_type is None, exc is None)
        return self.keep


with Quiet() as q:
    print("body", q is not None)
with Swallow(True):
    raise ValueError("gone")
print("after the suppressed error")
try:
    with Swallow(False):
        raise KeyError("kept")
except KeyError as err:
    print("caught", err)
with Swallow(False):
    print("no error")
