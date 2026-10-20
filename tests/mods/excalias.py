# Builtin exception classes by other names, as lib's _thread binds error (tests/programs/exceptions/exc_builtin_alias.py)
from builtins import KeyError as Missing
from builtins import RuntimeError as error


def fail(k: int) -> None:
    if k == 0:
        raise error("from excalias")
    raise Missing("k")
