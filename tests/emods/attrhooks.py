# Classes whose special methods CPython calls as their objects' attributes are read, assigned and
# deleted, and exception classes that define or inherit one: each is an error only where the
# program uses it (tests/errors/imports/import_*attr*.py)
class Lazy:
    def __init__(self, full: bool) -> None:
        if full:
            self.depth = 3

    def __getattr__(self, name: str) -> int:
        return 0


class Logged:
    def __init__(self, x: int) -> None:
        self.x = x

    def __getattribute__(self, name: str) -> int:
        print("get", name)
        return object.__getattribute__(self, name)


class Frozen:
    def __init__(self, x: int) -> None:
        self.x = x

    def __setattr__(self, name: str, v: int) -> None:
        raise AttributeError(f"cannot set {name}")


class Kept:
    def __init__(self, x: int) -> None:
        self.x = x

    def __delattr__(self, name: str) -> None:
        print("kept", name)


class LazyError(Exception):
    def __init__(self, msg: str, full: bool) -> None:
        super().__init__(msg)
        if full:
            self.depth = 3

    def __getattr__(self, name: str) -> int:
        return 0


class LoggedError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.code = 1

    def __getattribute__(self, name: str) -> object:
        print("get", name)
        return object.__getattribute__(self, name)


class LoggedRetry(LoggedError):
    "inherits LoggedError.__getattribute__"


class FrozenError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.tries = 1

    def __setattr__(self, name: str, v: int) -> None:
        raise AttributeError(f"cannot set {name}")


class FrozenRetry(FrozenError):
    "inherits FrozenError.__setattr__"


class KeptError(Exception):
    def __delattr__(self, name: str) -> None:
        print("kept", name)


class SealedError(Exception):
    "a class attribute binds the hook as a def does (CPython calls 0, a TypeError)"
    __setattr__ = 0

    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.code = 2


def double(x: int) -> int:
    return 2 * x
