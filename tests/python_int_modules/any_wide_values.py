# pystachy: python-int
# Producers and typed consumers for the mixed-module Any/wide-int regressions.


def make(bits: int) -> int:
    return 2 ** bits


def keep(value: int) -> int:
    return value


def keep_optional(value: int | None) -> int | None:
    return value


class Holder:
    def __init__(self, value: int) -> None:
        self.value = value

    def get(self) -> int:
        return self.value

    def set(self, value: int) -> None:
        self.value = value


def closure(value: int):
    def read() -> int:
        return value
    return read
