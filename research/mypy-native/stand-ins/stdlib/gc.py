# Probe stub: the collector controls mypy calls (mypy/build.py).
def set_threshold(a: int, b: int = 0, c: int = 0) -> None:
    pass


def disable() -> None:
    pass


def enable() -> None:
    pass


def freeze() -> None:
    pass


def unfreeze() -> None:
    pass


def isenabled() -> bool:
    return True


def collect() -> int:
    return 0
