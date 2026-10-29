# Deliberately no dynamic-any directive: imported typed code transports identity.
from typing import Callable
def keep_int(value: int) -> int:
    return value


def keep_float(value: float) -> float:
    alias = value
    return alias


VALUE = float("nan")


def default(value: float = VALUE) -> float:
    return value


class Pair:
    def __init__(self) -> None:
        value = float("nan")
        self.a: float = value
        self.b: float = value


def capture(value: float | None) -> Callable[[], float | None]:
    alias = value

    def read() -> float | None:
        return alias

    return read
