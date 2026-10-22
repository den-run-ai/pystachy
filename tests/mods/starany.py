# Defs whose *args or **kwargs are annotated Any are typed per call, as unannotated ones;
# this regression originated in the former pyfiglet port. An untypable annotation (complex) is left
# out, as a def with such a plain parameter is, so an error only where the program calls it
from typing import Any


def report(msg: str, **kwargs: Any) -> str:
    return msg + str(len(kwargs))


def collect(*args: Any) -> int:
    return len(args)


def double(x: int, **kwargs: int) -> int:
    return x * 2 + len(kwargs)


def scale(*args: complex) -> int:
    return len(args)
