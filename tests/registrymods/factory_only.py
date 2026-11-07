# pystachy: dynamic-any
from typing import Any


events: list[str] = []
shared: list[Any] = [1, "default"]
stable = 11


def make_default() -> int:
    events.append("default")
    return int("123456")


def increment(value: int) -> int:
    return value + 1


def transform(value: int) -> int:
    return increment(value)


class Imported:
    def __init__(self, value: int = make_default(), *, data: list[Any] = shared) -> None:
        events.append("init")
        self.original = value
        self.value = transform(value)
        self.data = data


class Empty:
    pass


def unsupported(value: int) -> int:
    return eval("value + 1")


class ColdBody:
    def __init__(self, value: int) -> None:
        self.value = value
        eval("value + 1")


class ColdHelper:
    def __init__(self, value: int) -> None:
        self.value = unsupported(value)


class ColdHints:
    def __init__(self, value: int) -> None:
        global stable
        stable = "unused"
        self.value = value
        eval("value + 1")


class ColdProtocol:
    def __init__(self, value: int) -> None:
        self.value = value

    def __repr__(self) -> str:
        return eval("'unused repr'")


class ColdNominal:
    def __init__(self, value: ColdProtocol) -> None:
        self.value = value


class Handler:
    def __init__(self, value: int) -> None:
        self.value = value

    def action(self) -> int:
        return unsupported(self.value)


class ColdDispatch:
    def __init__(self, value: Any) -> None:
        self.value: int = value.action()
