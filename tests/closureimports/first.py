from typing import Callable

A = 1


def value() -> int:
    return A


def factory() -> Callable[[], int]:
    import closureimports.second as local

    def inner() -> int:
        return local.A

    return inner
